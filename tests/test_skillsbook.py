"""Pruebas de Skills Book: solo stdlib, `python3 -m unittest discover tests`."""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skillsbook import __main__ as main  # noqa: E402
from skillsbook import frontmatter  # noqa: E402
from skillsbook.server import serve  # noqa: E402
from skillsbook.store import Conflict, NotFound, SkillStore, StoreError, slugify  # noqa: E402


class FrontmatterTests(unittest.TestCase):
    def test_parses_scalars_and_inline_lists(self):
        meta, body = frontmatter.parse(
            '---\nname: Revisar PRs\ndescription: "Hace: cosas"\ntags: [git, review]\n---\n\n# Hola\n'
        )
        self.assertEqual(meta["name"], "Revisar PRs")
        self.assertEqual(meta["description"], "Hace: cosas")
        self.assertEqual(meta["tags"], ["git", "review"])
        self.assertEqual(body.strip(), "# Hola")

    def test_parses_block_lists(self):
        meta, _ = frontmatter.parse("---\nagents:\n  - claude\n  - opencode\n---\ncuerpo\n")
        self.assertEqual(meta["agents"], ["claude", "opencode"])

    def test_round_trip_keeps_values(self):
        original = {"name": "X", "description": "con: dos puntos", "tags": ["a", "b"]}
        meta, body = frontmatter.parse(frontmatter.dump(original, "cuerpo"))
        self.assertEqual(meta, original)
        self.assertEqual(body.strip(), "cuerpo")

    def test_document_without_frontmatter(self):
        meta, body = frontmatter.parse("# solo markdown\n")
        self.assertEqual(meta, {})
        self.assertEqual(body.strip(), "# solo markdown")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = SkillStore(self.tmp / "skills")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, slug="demo", **kwargs):
        data = {"slug": slug, "name": slug.title(), "description": "Una skill de prueba."}
        data.update(kwargs)
        return self.store.create_skill(data)

    def test_create_writes_skill_file_on_disk(self):
        skill = self.make(agents=["claude", "opencode"], tags=["git"], folders=["scripts"])
        path = self.store.root / "demo" / "SKILL.md"
        self.assertTrue(path.is_file())
        self.assertIn("agents: [claude, opencode]", path.read_text())
        self.assertTrue((self.store.root / "demo" / "scripts").is_dir())
        self.assertEqual(skill["agents"], ["claude", "opencode"])

    def test_description_is_required(self):
        with self.assertRaises(StoreError):
            self.store.create_skill({"slug": "vacia", "name": "Vacia", "description": "  "})

    def test_duplicate_slug_conflicts(self):
        self.make()
        with self.assertRaises(Conflict):
            self.make()

    def test_invalid_slug_rejected(self):
        for bad in ["Con Mayus", "../fuera", "acentós", "-guion"]:
            with self.assertRaises(StoreError):
                self.store.create_skill({"slug": bad, "name": "x", "description": "y"})

    def test_empty_slug_falls_back_to_the_name(self):
        skill = self.store.create_skill({"slug": "", "name": "Revisión de Código", "description": "y"})
        self.assertEqual(skill["slug"], "revision-de-codigo")

    def test_update_changes_metadata_and_body(self):
        self.make(agents=["claude"], tags=["git"])
        updated = self.store.update_skill("demo", {"description": "Nueva", "tags": [], "body": "# Nuevo"})
        self.assertEqual(updated["description"], "Nueva")
        self.assertEqual(updated["tags"], [])
        self.assertEqual(updated["body"].strip(), "# Nuevo")
        self.assertEqual(updated["agents"], ["claude"])

    def test_update_preserves_unknown_frontmatter(self):
        self.make()
        path = self.store.root / "demo" / "SKILL.md"
        meta, body = frontmatter.parse(path.read_text())
        meta["x-origen"] = "importada"
        path.write_text(frontmatter.dump(meta, body))
        self.store.update_skill("demo", {"name": "Otro"})
        self.assertEqual(self.store.get_skill("demo")["extra"]["x-origen"], "importada")

    def test_rename_moves_the_folder(self):
        self.make()
        self.store.update_skill("demo", {"slug": "demo-2"})
        self.assertTrue((self.store.root / "demo-2").is_dir())
        self.assertFalse((self.store.root / "demo").exists())

    def test_delete_removes_everything(self):
        self.make()
        self.store.write_file("demo", "scripts/run.sh", "#!/bin/sh\necho hola\n")
        self.store.delete_skill("demo")
        self.assertFalse((self.store.root / "demo").exists())
        with self.assertRaises(NotFound):
            self.store.get_skill("demo")

    def test_duplicate_skill_copies_files(self):
        self.make()
        self.store.write_file("demo", "references/notas.md", "hola")
        copy = self.store.duplicate_skill("demo")
        self.assertTrue((self.store.root / copy["slug"] / "references" / "notas.md").is_file())
        self.assertIn("copia", copy["name"])

    # ------------------------------------------------------------- archivos
    def test_files_and_folders_lifecycle(self):
        self.make()
        self.store.create_folder("demo", "scripts/util")
        self.store.write_file("demo", "scripts/util/build.py", "print('hi')\n")
        tree = self.store.tree("demo")
        names = {node["name"] for node in tree}
        self.assertIn("scripts", names)
        self.assertEqual(self.store.read_file("demo", "scripts/util/build.py")["content"], "print('hi')\n")

        self.store.move_path("demo", "scripts/util/build.py", "scripts/build.py")
        self.assertTrue((self.store.root / "demo" / "scripts" / "build.py").is_file())

        self.store.delete_path("demo", "scripts")
        self.assertFalse((self.store.root / "demo" / "scripts").exists())

    def test_shell_scripts_become_executable(self):
        self.make()
        self.store.write_file("demo", "scripts/run.sh", "#!/bin/sh\necho hola\n")
        path = self.store.root / "demo" / "scripts" / "run.sh"
        self.assertTrue(path.stat().st_mode & 0o111)

    def test_skill_file_cannot_be_deleted(self):
        self.make()
        with self.assertRaises(StoreError):
            self.store.delete_path("demo", "SKILL.md")

    def test_binary_files_are_flagged_not_editable(self):
        self.make()
        self.store.write_binary("demo", "assets/logo.png", b"\x89PNG\r\n\x1a\n\x00\x01")
        payload = self.store.read_file("demo", "assets/logo.png")
        self.assertFalse(payload["editable"])

    def test_path_traversal_is_blocked(self):
        self.make()
        outside = self.tmp / "secreto.txt"
        outside.write_text("no tocar")
        for bad in ["../secreto.txt", "scripts/../../secreto.txt", "..\\secreto.txt"]:
            with self.assertRaises(StoreError):
                self.store.write_file("demo", bad, "hackeado")
        self.assertEqual(outside.read_text(), "no tocar")

    def test_absolute_paths_stay_inside_the_skill(self):
        self.make()
        self.store.write_file("demo", "/etc/passwd", "inocuo")
        self.assertTrue((self.store.root / "demo" / "etc" / "passwd").is_file())

    def test_symlink_escape_is_blocked(self):
        self.make()
        outside = self.tmp / "fuera"
        outside.mkdir()
        (self.store.root / "demo" / "link").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(StoreError):
            self.store.write_file("demo", "link/x.txt", "no")

    # ------------------------------------------------------- import/export
    def test_export_and_import_round_trip(self):
        self.make(tags=["git"])
        self.store.write_file("demo", "scripts/run.sh", "echo hola\n")
        blob = self.store.export_zip("demo")
        imported = self.store.import_zip(blob)
        self.assertEqual(len(imported), 1)
        other = imported[0]
        self.assertNotEqual(other, "demo")
        self.assertEqual(self.store.read_file(other, "scripts/run.sh")["content"], "echo hola\n")

    def test_import_zip_with_several_skills(self):
        self.make("uno")
        self.make("dos")
        imported = self.store.import_zip(self.store.export_all_zip())
        self.assertEqual(len(imported), 2)

    def test_import_zip_ignores_traversal_entries(self):
        import io
        import zipfile

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("mala/SKILL.md", "---\nname: Mala\ndescription: x\n---\ncuerpo\n")
            archive.writestr("mala/../../evil.txt", "boom")
        self.store.import_zip(buffer.getvalue())
        self.assertFalse((self.tmp / "evil.txt").exists())
        self.assertFalse((self.store.root.parent / "evil.txt").exists())

    def test_import_folder_from_disk(self):
        source = self.tmp / "externa"
        (source / "mi-skill").mkdir(parents=True)
        (source / "mi-skill" / "SKILL.md").write_text(
            "---\nname: Mi skill\ndescription: importada\n---\n\ncuerpo\n"
        )
        (source / "mi-skill" / "scripts").mkdir()
        (source / "mi-skill" / "scripts" / "a.py").write_text("x = 1\n")
        imported = self.store.import_folder(str(source))
        self.assertEqual(imported, ["mi-skill"])
        self.assertEqual(self.store.get_skill("mi-skill")["name"], "Mi skill")

    # -------------------------------------------------------------- varios
    def test_search_finds_text_inside_files(self):
        self.make()
        self.store.write_file("demo", "references/guia.md", "usa ripgrep para buscar\n")
        results = self.store.search("ripgrep")
        self.assertEqual(results[0]["slug"], "demo")
        self.assertEqual(results[0]["matches"][0]["path"], "references/guia.md")

    def test_stats_counts_agents_and_tags(self):
        self.make("uno", agents=["claude"], tags=["git"])
        self.make("dos", agents=["claude", "chatgpt"], tags=["git", "docs"])
        stats = self.store.stats()
        self.assertEqual(stats["count"], 2)
        self.assertEqual(stats["agents"]["claude"], 2)
        self.assertEqual(stats["tags"]["git"], 2)

    def test_slugify(self):
        self.assertEqual(slugify("Revisión de Código!"), "revision-de-codigo")


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.httpd, cls.store = serve(str(cls.tmp / "skills"), "127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def call(self, path, method="GET", body=None):
        request = urllib.request.Request(
            self.base + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request) as response:
                raw = response.read()
                ctype = response.headers.get("Content-Type", "")
                return response.status, (json.loads(raw) if "json" in ctype else raw)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_full_http_lifecycle(self):
        status, created = self.call("/api/skills", "POST", {
            "slug": "api-demo", "name": "Api Demo", "description": "desde http", "agents": ["claude"],
        })
        self.assertEqual(status, 201)
        self.assertEqual(created["slug"], "api-demo")

        status, listing = self.call("/api/skills")
        self.assertEqual(status, 200)
        self.assertIn("api-demo", [skill["slug"] for skill in listing["skills"]])

        status, _ = self.call("/api/skills/api-demo/file", "PUT",
                              {"path": "scripts/x.py", "content": "print(1)\n"})
        self.assertEqual(status, 200)

        status, payload = self.call("/api/skills/api-demo/file?path=scripts/x.py")
        self.assertEqual(payload["content"], "print(1)\n")

        status, blob = self.call("/api/skills/api-demo/export")
        self.assertEqual(status, 200)
        self.assertTrue(blob.startswith(b"PK"))

        status, updated = self.call("/api/skills/api-demo", "PUT", {"name": "Renombrada"})
        self.assertEqual(updated["name"], "Renombrada")

        status, _ = self.call("/api/skills/api-demo", "DELETE")
        self.assertEqual(status, 200)
        status, _ = self.call("/api/skills/api-demo")
        self.assertEqual(status, 404)

    def test_binary_upload_over_http(self):
        self.call("/api/skills", "POST", {"slug": "bin-demo", "name": "Bin", "description": "x"})
        blob = base64.b64encode(b"\x00\x01\x02binario").decode()
        status, _ = self.call("/api/skills/bin-demo/file", "PUT", {"path": "assets/a.bin", "base64": blob})
        self.assertEqual(status, 200)
        status, payload = self.call("/api/skills/bin-demo/file?path=assets/a.bin")
        self.assertFalse(payload["editable"])

    def test_errors_come_back_as_json(self):
        status, payload = self.call("/api/skills/no-existe")
        self.assertEqual(status, 404)
        self.assertIn("error", payload)

        status, payload = self.call("/api/skills", "POST", {"slug": "sin-desc", "name": "x"})
        self.assertEqual(status, 400)

    def test_traversal_over_http_is_rejected(self):
        self.call("/api/skills", "POST", {"slug": "seg", "name": "Seg", "description": "x"})
        status, payload = self.call("/api/skills/seg/file?path=../../../etc/passwd")
        self.assertIn(status, (400, 404))

    def test_index_is_served(self):
        with urllib.request.urlopen(self.base + "/") as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"Skills Book", response.read())

    def test_healthz_answers_without_token(self):
        status, payload = self.call("/healthz")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])

    def test_path_import_allowed_by_default(self):
        self.assertTrue(self.call("/api/stats")[1]["path_import"])


class DeploymentTests(unittest.TestCase):
    """Lo que cambia al publicar la app en la LAN: token y candados."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.httpd, cls.store = serve(
            str(cls.tmp / "skills"), "127.0.0.1", 0,
            token="secreto-de-prueba", allow_path_import=False,
        )
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def call(self, path, method="GET", body=None, headers=None):
        request = urllib.request.Request(
            self.base + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            with urllib.request.urlopen(request) as response:
                raw = response.read()
                ctype = response.headers.get("Content-Type", "")
                return response.status, (json.loads(raw) if "json" in ctype else raw)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    @staticmethod
    def basic(password, user="skills"):
        pair = base64.b64encode(f"{user}:{password}".encode()).decode()
        return {"Authorization": f"Basic {pair}"}

    def test_without_credentials_everything_is_401(self):
        for path in ("/", "/api/skills", "/api/stats"):
            status, _ = self.call(path)
            self.assertEqual(status, 401, path)

    def test_wrong_token_is_rejected(self):
        status, _ = self.call("/api/skills", headers=self.basic("otro"))
        self.assertEqual(status, 401)

    def test_basic_auth_with_the_token_opens_the_door(self):
        status, payload = self.call("/api/skills", headers=self.basic("secreto-de-prueba"))
        self.assertEqual(status, 200)
        self.assertIn("skills", payload)

    def test_token_header_also_works(self):
        status, _ = self.call("/api/stats", headers={"X-Skillsbook-Token": "secreto-de-prueba"})
        self.assertEqual(status, 200)

    def test_healthz_stays_open_for_the_healthcheck(self):
        status, payload = self.call("/healthz")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])

    def test_folder_import_is_refused_when_disabled(self):
        status, payload = self.call(
            "/api/import", "POST", {"path": "/etc"},
            headers=self.basic("secreto-de-prueba"),
        )
        self.assertEqual(status, 403)
        self.assertIn("error", payload)

    def test_zip_import_still_works_when_paths_are_off(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("traida/SKILL.md", "---\nname: Traida\n---\n\ncuerpo\n")
        status, payload = self.call(
            "/api/import", "POST",
            {"zip_base64": base64.b64encode(buffer.getvalue()).decode()},
            headers=self.basic("secreto-de-prueba"),
        )
        self.assertEqual(status, 201)
        self.assertEqual(payload["imported"], ["traida"])

    def test_stats_tell_the_ui_that_path_import_is_off(self):
        _, payload = self.call("/api/stats", headers=self.basic("secreto-de-prueba"))
        self.assertFalse(payload["path_import"])


class LaunchTests(unittest.TestCase):
    """Decisiones de arranque: local abre navegador, LAN no salta de puerto."""

    def test_loopback_detection(self):
        for host in ("127.0.0.1", "localhost", "::1", "127.0.1.1"):
            self.assertTrue(main.is_loopback(host), host)
        for host in ("0.0.0.0", "192.168.1.50", "::", "no-es-una-ip"):
            self.assertFalse(main.is_loopback(host), host)

    def test_env_flag_reads_the_usual_spellings(self):
        for raw in ("1", "true", "YES", "on", "si"):
            os.environ["SKILLSBOOK_TEST_FLAG"] = raw
            self.assertTrue(main.env_flag("SKILLSBOOK_TEST_FLAG"))
        for raw in ("0", "false", "no", "off"):
            os.environ["SKILLSBOOK_TEST_FLAG"] = raw
            self.assertFalse(main.env_flag("SKILLSBOOK_TEST_FLAG", default=True))
        os.environ.pop("SKILLSBOOK_TEST_FLAG", None)
        self.assertTrue(main.env_flag("SKILLSBOOK_TEST_FLAG", default=True))

    def test_strict_port_fails_instead_of_moving(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen(1)
            port = taken.getsockname()[1]
            with self.assertRaises(SystemExit):
                main._pick_port("127.0.0.1", port, strict=True)

    def test_without_strict_it_hops_to_the_next_free_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen(1)
            port = taken.getsockname()[1]
            self.assertNotEqual(main._pick_port("127.0.0.1", port), port)

    def test_env_configures_host_port_and_library(self):
        os.environ["SKILLSBOOK_HOST"] = "0.0.0.0"
        os.environ["SKILLSBOOK_PORT"] = "9100"
        try:
            args = main.build_parser().parse_args([])
            self.assertEqual(args.host, "0.0.0.0")
            self.assertEqual(args.port, 9100)
        finally:
            os.environ.pop("SKILLSBOOK_HOST", None)
            os.environ.pop("SKILLSBOOK_PORT", None)

    def test_token_can_come_from_a_file(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            secret = tmp / "token.txt"
            secret.write_text("desde-fichero\n", encoding="utf-8")
            os.environ["SKILLSBOOK_TOKEN_FILE"] = str(secret)
            self.assertEqual(main.default_token(), "desde-fichero")
        finally:
            os.environ.pop("SKILLSBOOK_TOKEN_FILE", None)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
