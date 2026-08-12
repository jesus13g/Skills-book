/* Skills Book — UI logic. Vanilla JS, no build step. */
(function () {
  'use strict';

  const esc = window.md.esc;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  /* Simbología: solo SVG del sprite de index.html, nunca emojis. */
  const ic = (name, extra = '') =>
    `<svg class="ic ${extra}" aria-hidden="true"><use href="#i-${name}"/></svg>`;

  const state = {
    skills: [],
    stats: null,
    current: null,        // full skill object
    tab: 'view',
    query: '',
    filters: { agents: new Set(), tags: new Set() },
    file: null,           // { path, content, editable, size }
    fileDirty: false,
    searchResults: null,
  };

  /* ------------------------------------------------------------------ api */
  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
      ...options,
    });
    const type = response.headers.get('Content-Type') || '';
    if (!type.includes('application/json')) {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response;
    }
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  const send = (path, method, body) =>
    api(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

  /* --------------------------------------------------------------- toasts */
  function toast(message, isError = false) {
    const node = document.createElement('div');
    node.className = 'toast' + (isError ? ' err' : '');
    node.innerHTML = `${ic(isError ? 'alert' : 'check', 'ic-sm')}<span></span>`;
    $('span', node).textContent = message;
    $('#toasts').appendChild(node);
    setTimeout(() => node.remove(), isError ? 6000 : 3000);
  }

  const fail = (error) => toast(error.message || String(error), true);

  function humanSize(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / Math.pow(1024, index);
    return `${index === 0 ? value : value.toFixed(1)} ${units[index]}`;
  }

  /* --------------------------------------------------------------- modals */
  function modal(title, innerHtml, onMount) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true">
        <div class="modal-head"><h3>${esc(title)}</h3></div>
        <div class="modal-body">${innerHtml}</div>
      </div>`;
    const close = () => backdrop.remove();
    backdrop.addEventListener('mousedown', (event) => {
      if (event.target === backdrop) close();
    });
    document.addEventListener('keydown', function onKey(event) {
      if (event.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); }
    });
    $('#modal-root').appendChild(backdrop);
    onMount($('.modal', backdrop), close);
    const firstInput = $('input, textarea', backdrop);
    if (firstInput) firstInput.focus();
    return close;
  }

  function ask(title, label, value = '') {
    return new Promise((resolve) => {
      modal(title, `
        <div class="form">
          <div class="field"><label>${esc(label)}</label><input id="ask-input" value="${esc(value)}"></div>
          <div class="form-actions">
            <button class="primary" id="ask-ok">${ic('check', 'ic-sm')}Aceptar</button>
            <button class="ghost" id="ask-cancel">Cancelar</button>
          </div>
        </div>`, (root, close) => {
        const input = $('#ask-input', root);
        const ok = () => { close(); resolve(input.value.trim() || null); };
        $('#ask-ok', root).onclick = ok;
        $('#ask-cancel', root).onclick = () => { close(); resolve(null); };
        input.onkeydown = (event) => { if (event.key === 'Enter') ok(); };
      });
    });
  }

  function confirmDanger(title, message, confirmLabel = 'Borrar') {
    return new Promise((resolve) => {
      modal(title, `
        <p class="muted">${esc(message)}</p>
        <div class="form-actions">
          <button class="danger" id="c-ok">${ic('trash', 'ic-sm')}${esc(confirmLabel)}</button>
          <button class="ghost" id="c-no">Cancelar</button>
        </div>`, (root, close) => {
        $('#c-ok', root).onclick = () => { close(); resolve(true); };
        $('#c-no', root).onclick = () => { close(); resolve(false); };
      });
    });
  }

  /* ------------------------------------------------------------- sidebar */
  async function refresh(selectSlug) {
    const [list, stats] = await Promise.all([api('/api/skills'), api('/api/stats')]);
    state.skills = list.skills;
    state.stats = stats;
    $('#library-path').textContent = stats.root;
    renderFilters();
    renderList();
    renderEmptyStats();
    if (selectSlug) await openSkill(selectSlug);
    else if (state.current && !state.skills.some((s) => s.slug === state.current.slug)) closeSkill();
  }

  function renderFilters() {
    const agents = Object.keys(state.stats.agents || {}).filter((a) => a !== 'sin-agente');
    const tags = Object.keys(state.stats.tags || {}).slice(0, 12);
    const chip = (label, kind, count) =>
      `<button class="chip${state.filters[kind].has(label) ? ' on' : ''}" data-filter="${kind}" data-value="${esc(label)}">${
        esc(label)}${count ? `<span class="count">${count}</span>` : ''}</button>`;
    $('#filters').innerHTML =
      agents.map((a) => chip(a, 'agents', state.stats.agents[a])).join('') +
      tags.map((t) => chip('#' + t, 'tags', 0)).join('');
    $$('#filters .chip').forEach((node) => {
      node.onclick = () => {
        const kind = node.dataset.filter;
        const value = kind === 'tags' ? node.dataset.value.slice(1) : node.dataset.value;
        const set = state.filters[kind];
        if (set.has(kind === 'tags' ? '#' + value : value)) set.delete(kind === 'tags' ? '#' + value : value);
        else set.add(kind === 'tags' ? '#' + value : value);
        renderFilters();
        renderList();
      };
    });
  }

  function visibleSkills() {
    const query = state.query.toLowerCase();
    return state.skills.filter((skill) => {
      if (query) {
        const haystack = [skill.name, skill.slug, skill.description, skill.tags.join(' '), skill.agents.join(' ')]
          .join(' ').toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      for (const agent of state.filters.agents) {
        if (!skill.agents.includes(agent)) return false;
      }
      for (const tag of state.filters.tags) {
        if (!skill.tags.includes(tag.replace(/^#/, ''))) return false;
      }
      return true;
    });
  }

  function renderList() {
    const skills = visibleSkills();
    if (!skills.length) {
      $('#skill-list').innerHTML = `<p class="list-empty">${
        state.skills.length ? 'Ninguna skill coincide' : 'Biblioteca vacía'}</p>`;
      return;
    }
    $('#skill-list').innerHTML = skills.map((skill) => `
      <article class="skill-card${state.current && state.current.slug === skill.slug ? ' on' : ''}" data-slug="${esc(skill.slug)}">
        <h3>${esc(skill.name)}</h3>
        <p>${esc(skill.description || 'Sin descripción')}</p>
        <div class="meta">
          ${skill.agents.map((a) => `<span class="tag agent">${esc(a)}</span>`).join('')}
          ${skill.tags.slice(0, 3).map((t) => `<span class="tag">${ic('hash')}${esc(t)}</span>`).join('')}
          ${skill.file_count > 1 ? `<span class="tag">${ic('file')}${skill.file_count}</span>` : ''}
        </div>
      </article>`).join('');
    $$('#skill-list .skill-card').forEach((node) => {
      node.onclick = () => openSkill(node.dataset.slug);
    });
  }

  function renderEmptyStats() {
    const stats = state.stats;
    $('#empty-stats').innerHTML = `
      <div><strong>${stats.count}</strong><span>skills</span></div>
      <div><strong>${stats.files}</strong><span>archivos</span></div>
      <div><strong>${Object.keys(stats.agents).filter((a) => a !== 'sin-agente').length}</strong><span>agentes</span></div>`;
  }

  /* -------------------------------------------------------------- detail */
  function closeSkill() {
    state.current = null;
    state.file = null;
    location.hash = '';
    $('#detail').classList.add('hidden');
    $('#empty').classList.remove('hidden');
    renderList();
  }

  async function openSkill(slug, tab) {
    try {
      state.current = await api(`/api/skills/${encodeURIComponent(slug)}`);
      state.tab = tab || 'view';
      state.file = null;
      state.fileDirty = false;
      state.searchResults = null;
      location.hash = '/' + slug;
      $('#empty').classList.add('hidden');
      $('#detail').classList.remove('hidden');
      renderDetail();
      renderList();
    } catch (error) { fail(error); }
  }

  function renderDetail() {
    const skill = state.current;
    const tabs = [['view', 'Contenido', 'eye'], ['files', 'Archivos', 'tree'], ['edit', 'Editar', 'edit']];
    $('#detail').innerHTML = `
      <div class="detail-head">
        <div class="detail-title">
          <div>
            <h2>${esc(skill.name)}</h2>
            <span class="slug">
              <span><b>${esc(skill.slug)}</b>/SKILL.md</span>
              <span>${skill.file_count} archivos</span>
              <span>${humanSize(skill.size_bytes)}</span>
            </span>
          </div>
          <div class="detail-actions">
            <button class="ghost" data-act="duplicate">${ic('copy', 'ic-sm')}Duplicar</button>
            <button class="ghost" data-act="export">${ic('export', 'ic-sm')}Exportar</button>
            <button class="danger square" data-act="delete" title="Borrar skill" aria-label="Borrar skill">${ic('trash')}</button>
            <button class="ghost square" data-act="close" title="Cerrar" aria-label="Cerrar">${ic('close')}</button>
          </div>
        </div>
        <p class="detail-desc">${esc(skill.description || 'Sin descripción')}</p>
        <div class="detail-meta">
          ${skill.agents.map((a) => `<span class="tag agent">${esc(a)}</span>`).join('')}
          ${skill.tags.map((t) => `<span class="tag">${ic('hash')}${esc(t)}</span>`).join('')}
          ${skill.version ? `<span class="tag">v${esc(skill.version)}</span>` : ''}
          ${skill.author ? `<span class="tag">${esc(skill.author)}</span>` : ''}
          ${skill.license ? `<span class="tag">${esc(skill.license)}</span>` : ''}
          ${skill.updated ? `<span class="tag">${esc(skill.updated.replace('T', ' '))}</span>` : ''}
        </div>
        <div class="tabs">${tabs.map(([key, label, icon]) =>
          `<button class="tab${state.tab === key ? ' on' : ''}" data-tab="${key}">${ic(icon, 'ic-sm')}${label}</button>`).join('')}</div>
      </div>
      <div class="tab-body" id="tab-body"></div>`;

    $$('#detail .tab').forEach((node) => {
      node.onclick = () => { state.tab = node.dataset.tab; renderDetail(); };
    });
    $$('#detail [data-act]').forEach((node) => {
      node.onclick = () => detailAction(node.dataset.act);
    });

    if (state.tab === 'view') renderView();
    if (state.tab === 'files') renderFiles();
    if (state.tab === 'edit') renderEdit();
  }

  async function detailAction(action) {
    const skill = state.current;
    try {
      if (action === 'duplicate') {
        const copy = await send(`/api/skills/${skill.slug}/duplicate`, 'POST', {});
        toast(`Duplicada como ${copy.slug}`);
        await refresh(copy.slug);
      } else if (action === 'export') {
        window.location.href = `/api/skills/${skill.slug}/export`;
      } else if (action === 'close') {
        closeSkill();
      } else if (action === 'delete') {
        const sure = await confirmDanger(
          `Borrar "${skill.name}"`,
          `Se eliminará la carpeta ${skill.slug}/ con sus ${skill.file_count} archivos. Esta acción no se puede deshacer.`);
        if (!sure) return;
        await send(`/api/skills/${skill.slug}`, 'DELETE');
        toast('Skill borrada');
        state.current = null;
        await refresh();
        closeSkill();
      }
    } catch (error) { fail(error); }
  }

  function renderView() {
    const skill = state.current;
    const extras = Object.entries(skill.extra || {});
    const strip = []
      .concat(skill.allowed_tools.length
        ? [['allowed-tools', skill.allowed_tools.join(', ')]] : [])
      .concat(extras.map(([key, value]) => [key, String(value)]));
    $('#tab-body').innerHTML = `
      <div class="md">${window.md.render(skill.body || '_Esta skill todavía no tiene contenido._')}</div>
      ${strip.length ? `<div class="meta-strip">${strip.map(([key, value]) =>
        `<div><b>${esc(key)}</b> <span>${esc(value)}</span></div>`).join('')}</div>` : ''}`;
  }

  /* --------------------------------------------------------------- files */
  function treeHtml(nodes) {
    if (!nodes.length) return '<p class="list-empty">Sin archivos</p>';
    const item = (node) => node.type === 'dir'
      ? `<li>
          <div class="node" data-dir="${esc(node.path)}">
            ${ic('folder')}<span class="name">${esc(node.name)}</span>
            <span class="node-actions">
              <button class="icon" data-new-here="${esc(node.path)}" title="Nuevo archivo aquí" aria-label="Nuevo archivo aquí">${ic('plus', 'ic-sm')}</button>
              <button class="icon" data-rename="${esc(node.path)}" title="Renombrar" aria-label="Renombrar">${ic('edit', 'ic-sm')}</button>
              <button class="icon" data-delete="${esc(node.path)}" title="Borrar" aria-label="Borrar">${ic('trash', 'ic-sm')}</button>
            </span>
          </div>
          ${node.children.length ? `<ul>${node.children.map(item).join('')}</ul>` : ''}
        </li>`
      : `<li>
          <div class="node${state.file && state.file.path === node.path ? ' on' : ''}" data-file="${esc(node.path)}">
            ${ic(node.editable ? 'file' : 'binary')}<span class="name">${esc(node.name)}</span>
            <span class="size">${humanSize(node.size)}</span>
            <span class="node-actions">
              <button class="icon" data-download="${esc(node.path)}" title="Descargar" aria-label="Descargar">${ic('download', 'ic-sm')}</button>
              <button class="icon" data-rename="${esc(node.path)}" title="Renombrar o mover" aria-label="Renombrar o mover">${ic('edit', 'ic-sm')}</button>
              <button class="icon" data-delete="${esc(node.path)}" title="Borrar" aria-label="Borrar">${ic('trash', 'ic-sm')}</button>
            </span>
          </div>
        </li>`;
    return `<ul>${nodes.map(item).join('')}</ul>`;
  }

  function renderFiles() {
    const skill = state.current;
    $('#tab-body').innerHTML = `
      <div class="files">
        <div class="panel-box">
          <div class="panel-head">
            <span class="title">Árbol</span>
            <div class="tree-toolbar">
              <button class="ghost" data-tool="file" title="Nuevo archivo">${ic('file', 'ic-sm')}Archivo</button>
              <button class="ghost" data-tool="folder" title="Nueva carpeta">${ic('folder', 'ic-sm')}Carpeta</button>
              <button class="ghost square" data-tool="upload" title="Subir archivos" aria-label="Subir archivos">${ic('upload', 'ic-sm')}</button>
            </div>
          </div>
          <div class="tree">${treeHtml(skill.tree)}</div>
        </div>
        <div class="panel-box" id="editor-panel">
          <div class="binary-note">
            ${ic('corner')}
            Elige un archivo del árbol para verlo o editarlo
          </div>
        </div>
      </div>
      <input type="file" id="upload-input" multiple hidden>`;

    $$('#tab-body [data-file]').forEach((node) => {
      node.onclick = (event) => {
        if (event.target.closest('button')) return;
        openFile(node.dataset.file);
      };
    });
    $$('#tab-body [data-download]').forEach((node) => {
      node.onclick = () => {
        window.location.href =
          `/api/skills/${skill.slug}/raw?path=${encodeURIComponent(node.dataset.download)}`;
      };
    });
    $$('#tab-body [data-rename]').forEach((node) => {
      node.onclick = async () => {
        const from = node.dataset.rename;
        const to = await ask('Renombrar o mover', 'Nueva ruta dentro de la skill', from);
        if (!to || to === from) return;
        try {
          await send(`/api/skills/${skill.slug}/move`, 'POST', { path: from, to });
          toast('Movido');
          if (state.file && state.file.path === from) state.file = null;
          await reloadCurrent();
        } catch (error) { fail(error); }
      };
    });
    $$('#tab-body [data-delete]').forEach((node) => {
      node.onclick = async () => {
        const target = node.dataset.delete;
        if (!await confirmDanger('Borrar', `Se eliminará "${target}" de la skill.`)) return;
        try {
          await send(`/api/skills/${skill.slug}/file?path=${encodeURIComponent(target)}`, 'DELETE');
          if (state.file && state.file.path.startsWith(target)) state.file = null;
          toast('Borrado');
          await reloadCurrent();
        } catch (error) { fail(error); }
      };
    });
    $$('#tab-body [data-new-here]').forEach((node) => {
      node.onclick = () => newFile(node.dataset.newHere + '/');
    });
    $$('#tab-body [data-tool]').forEach((node) => {
      node.onclick = () => {
        if (node.dataset.tool === 'file') newFile('');
        if (node.dataset.tool === 'folder') newFolder();
        if (node.dataset.tool === 'upload') $('#upload-input').click();
      };
    });
    $('#upload-input').onchange = (event) => uploadFiles(Array.from(event.target.files));

    if (state.file) renderEditor();
  }

  async function reloadCurrent() {
    const keepPath = state.file && state.file.path;
    state.current = await api(`/api/skills/${state.current.slug}`);
    renderDetail();
    if (keepPath && state.tab === 'files') {
      try { await openFile(keepPath); } catch (_) { /* archivo ya no existe */ }
    }
    const summary = state.skills.find((s) => s.slug === state.current.slug);
    if (summary) Object.assign(summary, { file_count: state.current.file_count });
  }

  async function openFile(path) {
    if (state.fileDirty && !confirm('Hay cambios sin guardar. ¿Descartarlos?')) return;
    try {
      state.file = await api(`/api/skills/${state.current.slug}/file?path=${encodeURIComponent(path)}`);
      state.fileDirty = false;
      $$('#tab-body .node').forEach((node) => node.classList.toggle('on', node.dataset.file === path));
      renderEditor();
    } catch (error) { fail(error); }
  }

  function renderEditor() {
    const file = state.file;
    const panel = $('#editor-panel');
    if (!panel) return;
    const isImage = /\.(png|jpe?g|gif|webp|svg|avif)$/i.test(file.path);
    const url = `/api/skills/${state.current.slug}/raw?path=${encodeURIComponent(file.path)}`;

    const segments = file.path.split('/');
    const pathHtml = segments
      .map((part, index) => index === segments.length - 1 ? `<b>${esc(part)}</b>` : esc(part))
      .join('<span class="sep">/</span>');

    panel.innerHTML = `
      <div class="editor-head">
        ${ic(file.editable ? 'file' : 'binary', 'ic-sm')}
        <span class="path">${pathHtml}</span>
        <span class="dirty hidden" id="dirty-flag">${ic('dot')}sin guardar</span>
        ${file.editable ? `<button class="primary" id="save-file">${ic('save', 'ic-sm')}Guardar</button>` : ''}
        <button class="ghost square" id="download-file" title="Descargar" aria-label="Descargar">${ic('download', 'ic-sm')}</button>
      </div>
      ${file.editable
        ? `<textarea class="code" id="file-editor" spellcheck="false">${esc(file.content)}</textarea>`
        : `<div class="binary-note">
             ${isImage ? `<img src="${url}" alt="${esc(file.path)}">` : ic('binary')}
             <p>Archivo binario · ${humanSize(file.size)} · no editable aquí</p>
           </div>`}`;

    $('#download-file').onclick = () => { window.location.href = url; };
    if (!file.editable) return;

    const editor = $('#file-editor');
    editor.oninput = () => {
      state.fileDirty = true;
      $('#dirty-flag').classList.remove('hidden');
    };
    editor.onkeydown = (event) => {
      if (event.key === 'Tab') {
        event.preventDefault();
        const { selectionStart: start, selectionEnd: end } = editor;
        editor.value = editor.value.slice(0, start) + '  ' + editor.value.slice(end);
        editor.selectionStart = editor.selectionEnd = start + 2;
        state.fileDirty = true;
      }
    };
    $('#save-file').onclick = saveFile;
  }

  async function saveFile() {
    const editor = $('#file-editor');
    if (!editor || !state.file) return;
    try {
      await send(`/api/skills/${state.current.slug}/file`, 'PUT',
        { path: state.file.path, content: editor.value });
      state.file.content = editor.value;
      state.fileDirty = false;
      const flag = $('#dirty-flag');
      if (flag) flag.classList.add('hidden');
      toast(`Guardado ${state.file.path}`);
      if (state.file.path === 'SKILL.md') await refresh(state.current.slug);
    } catch (error) { fail(error); }
  }

  async function newFile(prefix) {
    const path = await ask('Nuevo archivo', 'Ruta dentro de la skill', prefix + 'notas.md');
    if (!path) return;
    try {
      await send(`/api/skills/${state.current.slug}/file`, 'PUT', { path, content: '' });
      toast('Archivo creado');
      await reloadCurrent();
      await openFile(path);
    } catch (error) { fail(error); }
  }

  async function newFolder() {
    const path = await ask('Nueva carpeta', 'Ruta dentro de la skill', 'scripts');
    if (!path) return;
    try {
      await send(`/api/skills/${state.current.slug}/folder`, 'POST', { path });
      toast('Carpeta creada');
      await reloadCurrent();
    } catch (error) { fail(error); }
  }

  function readAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  async function uploadFiles(files) {
    if (!files.length) return;
    const folder = await ask('Subir archivos', 'Carpeta destino (vacío = raíz de la skill)', 'assets');
    if (folder === null) return;
    for (const file of files) {
      try {
        const base64 = await readAsBase64(file);
        const path = folder ? `${folder}/${file.name}` : file.name;
        await send(`/api/skills/${state.current.slug}/file`, 'PUT', { path, base64 });
        toast(`Subido ${file.name}`);
      } catch (error) { fail(error); }
    }
    await reloadCurrent();
  }

  /* ---------------------------------------------------------------- edit */
  function agentPicker(selected) {
    const known = (state.stats.known_agents || []).concat(
      selected.filter((a) => !(state.stats.known_agents || []).includes(a)));
    return known.map((agent) => `
      <button type="button" class="chip${selected.includes(agent) ? ' on' : ''}" data-agent="${esc(agent)}">${esc(agent)}</button>`).join('');
  }

  function renderEdit() {
    const skill = state.current;
    $('#tab-body').innerHTML = `
      <form class="form" id="edit-form">
        <div class="row2">
          <div class="field">
            <label for="f-name">Nombre</label>
            <input id="f-name" value="${esc(skill.name)}" required>
          </div>
          <div class="field">
            <label for="f-slug">Identificador (carpeta)</label>
            <input id="f-slug" value="${esc(skill.slug)}" pattern="[a-z0-9]+((-|_)[a-z0-9]+)*">
            <span class="hint">Renombra la carpeta en disco.</span>
          </div>
        </div>
        <div class="field">
          <label for="f-desc">Descripción</label>
          <textarea id="f-desc" style="min-height:70px" required>${esc(skill.description)}</textarea>
          <span class="hint">Es lo que lee el agente para decidir si activa la skill: di qué hace y cuándo usarla.</span>
        </div>
        <div class="field">
          <label>Agentes compatibles</label>
          <div class="agent-picker" id="f-agents">${agentPicker(skill.agents)}</div>
        </div>
        <div class="row2">
          <div class="field">
            <label for="f-tags">Etiquetas</label>
            <input id="f-tags" value="${esc(skill.tags.join(', '))}" placeholder="testing, git, docs">
          </div>
          <div class="field">
            <label for="f-tools">Herramientas permitidas</label>
            <input id="f-tools" value="${esc(skill.allowed_tools.join(', '))}" placeholder="Read, Bash, Edit">
          </div>
        </div>
        <div class="row2">
          <div class="field"><label for="f-version">Versión</label><input id="f-version" value="${esc(skill.version)}"></div>
          <div class="field"><label for="f-author">Autor</label><input id="f-author" value="${esc(skill.author)}"></div>
        </div>
        <div class="field">
          <label for="f-license">Licencia</label>
          <input id="f-license" value="${esc(skill.license)}" placeholder="MIT">
        </div>
        <div class="field">
          <label for="f-body">Contenido de SKILL.md (markdown)</label>
          <textarea id="f-body" style="min-height:340px" spellcheck="false">${esc(skill.body)}</textarea>
          <span class="hint">Ctrl/Cmd + S para guardar.</span>
        </div>
        <div class="form-actions">
          <button class="primary" type="submit">${ic('save', 'ic-sm')}Guardar cambios</button>
          <button class="ghost" type="button" id="f-cancel">Descartar</button>
        </div>
      </form>`;

    $$('#f-agents .chip').forEach((node) => {
      node.onclick = () => node.classList.toggle('on');
    });
    $('#f-cancel').onclick = () => { state.tab = 'view'; renderDetail(); };
    $('#edit-form').onsubmit = async (event) => {
      event.preventDefault();
      await saveSkillForm();
    };
  }

  const splitList = (value) => value.split(',').map((item) => item.trim()).filter(Boolean);

  async function saveSkillForm() {
    const payload = {
      name: $('#f-name').value.trim(),
      slug: $('#f-slug').value.trim(),
      description: $('#f-desc').value.trim(),
      agents: $$('#f-agents .chip.on').map((node) => node.dataset.agent),
      tags: splitList($('#f-tags').value),
      allowed_tools: splitList($('#f-tools').value),
      version: $('#f-version').value.trim(),
      author: $('#f-author').value.trim(),
      license: $('#f-license').value.trim(),
      body: $('#f-body').value,
    };
    try {
      const updated = await send(`/api/skills/${state.current.slug}`, 'PUT', payload);
      toast('Cambios guardados');
      state.tab = 'view';
      await refresh(updated.slug);
    } catch (error) { fail(error); }
  }

  /* ----------------------------------------------------------- new skill */
  function newSkillModal() {
    modal('Nueva skill', `
      <form class="form" id="new-form">
        <div class="row2">
          <div class="field"><label for="n-name">Nombre</label><input id="n-name" placeholder="Revisar pull requests" required></div>
          <div class="field"><label for="n-slug">Identificador</label><input id="n-slug" placeholder="revisar-pull-requests"></div>
        </div>
        <div class="field">
          <label for="n-desc">Descripción</label>
          <textarea id="n-desc" style="min-height:70px" placeholder="Qué hace la skill y cuándo debe usarla el agente." required></textarea>
        </div>
        <div class="field"><label>Agentes</label><div class="agent-picker" id="n-agents">${agentPicker(['claude'])}</div></div>
        <div class="row2">
          <div class="field"><label for="n-tags">Etiquetas</label><input id="n-tags" placeholder="git, review"></div>
          <div class="field"><label for="n-folders">Carpetas iniciales</label><input id="n-folders" value="scripts, references"></div>
        </div>
        <div class="form-actions">
          <button class="primary" type="submit">${ic('plus', 'ic-sm')}Crear skill</button>
          <button class="ghost" type="button" id="n-cancel">Cancelar</button>
        </div>
      </form>`, (root, close) => {
      const name = $('#n-name', root);
      const slug = $('#n-slug', root);
      let slugTouched = false;
      slug.oninput = () => { slugTouched = true; };
      name.oninput = async () => {
        if (slugTouched) return;
        try {
          const data = await send('/api/slugify', 'POST', { name: name.value });
          if (!slugTouched) slug.value = data.slug;
        } catch (_) { /* sugerencia opcional */ }
      };
      $$('#n-agents .chip', root).forEach((node) => {
        node.onclick = () => node.classList.toggle('on');
      });
      $('#n-cancel', root).onclick = close;
      $('#new-form', root).onsubmit = async (event) => {
        event.preventDefault();
        try {
          const created = await send('/api/skills', 'POST', {
            name: name.value.trim(),
            slug: slug.value.trim(),
            description: $('#n-desc', root).value.trim(),
            agents: $$('#n-agents .chip.on', root).map((node) => node.dataset.agent),
            tags: splitList($('#n-tags', root).value),
            folders: splitList($('#n-folders', root).value),
          });
          close();
          toast(`Skill "${created.name}" creada`);
          await refresh(created.slug);
        } catch (error) { fail(error); }
      };
    });
  }

  /* -------------------------------------------------------------- import */
  function importModal() {
    modal('Importar skills', `
      <div class="form">
        <div class="field">
          <label>Desde un zip</label>
          <input type="file" id="i-zip" accept=".zip">
          <span class="hint">Acepta un zip con una skill (SKILL.md en la raíz) o con varias carpetas de skills.</span>
        </div>
        <div class="field">
          <label for="i-path">Desde una carpeta local</label>
          <input id="i-path" placeholder="~/.claude/skills">
          <span class="hint">Copia la carpeta (o cada subcarpeta con SKILL.md) a la biblioteca.</span>
        </div>
        <div class="form-actions">
          <button class="primary" id="i-go">${ic('import', 'ic-sm')}Importar</button>
          <button class="ghost" id="i-cancel">Cancelar</button>
        </div>
      </div>`, (root, close) => {
      $('#i-cancel', root).onclick = close;
      $('#i-go', root).onclick = async () => {
        const file = $('#i-zip', root).files[0];
        const path = $('#i-path', root).value.trim();
        try {
          let result;
          if (file) result = await send('/api/import', 'POST', { zip_base64: await readAsBase64(file) });
          else if (path) result = await send('/api/import', 'POST', { path });
          else return toast('Elige un zip o escribe una ruta.', true);
          close();
          toast(`Importadas ${result.imported.length} skills`);
          await refresh(result.imported[0]);
        } catch (error) { fail(error); }
      };
    });
  }

  /* -------------------------------------------------------------- search */
  async function deepSearch() {
    const query = state.query.trim();
    if (!query) return toast('Escribe algo en el buscador primero.', true);
    try {
      const data = await api(`/api/search?q=${encodeURIComponent(query)}`);
      state.current = null;
      $('#empty').classList.add('hidden');
      $('#detail').classList.remove('hidden');
      $('#detail').innerHTML = `
        <div class="detail-head">
          <div class="detail-title">
            <div>
              <h2>“${esc(query)}”</h2>
              <span class="slug">
                <span><b>${data.results.length}</b> skills con coincidencias en su contenido</span>
              </span>
            </div>
            <div class="detail-actions">
              <button class="ghost square" data-close-search title="Cerrar" aria-label="Cerrar">${ic('close')}</button>
            </div>
          </div>
          <div class="tabs"></div>
        </div>
        <div class="tab-body">${data.results.length ? data.results.map((hit) => `
          <div class="hit">
            <h4><a href="#/${esc(hit.slug)}" data-open="${esc(hit.slug)}">${esc(hit.name)}</a></h4>
            ${hit.matches.map((match) => `<div class="line">
              <span class="where">${esc(match.path)}:${match.line}</span> ${highlight(match.text, query)}
            </div>`).join('')}
          </div>`).join('') : '<p class="list-empty">Sin coincidencias</p>'}</div>`;
      $$('#detail [data-open]').forEach((node) => {
        node.onclick = (event) => { event.preventDefault(); openSkill(node.dataset.open); };
      });
      $('#detail [data-close-search]').onclick = closeSkill;
    } catch (error) { fail(error); }
  }

  function highlight(text, query) {
    const escaped = esc(text);
    const needle = esc(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return escaped.replace(new RegExp(needle, 'ig'), (found) => `<b>${found}</b>`);
  }

  /* ---------------------------------------------------------------- boot */
  function bindGlobal() {
    $('#search').oninput = (event) => { state.query = event.target.value; renderList(); };
    $('#search').onkeydown = (event) => { if (event.key === 'Enter') deepSearch(); };
    $('#btn-deep-search').onclick = deepSearch;
    $('#btn-new').onclick = newSkillModal;
    $('#btn-import').onclick = importModal;
    $('#btn-export-all').onclick = () => { window.location.href = '/api/export'; };
    $('[data-action="new"]').onclick = newSkillModal;

    document.addEventListener('keydown', (event) => {
      const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
      if (event.key === '/' && !typing) {
        event.preventDefault();
        $('#search').focus();
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        if ($('#file-editor')) saveFile();
        else if ($('#edit-form')) saveSkillForm();
      }
    });

    window.addEventListener('beforeunload', (event) => {
      if (state.fileDirty) { event.preventDefault(); event.returnValue = ''; }
    });
  }

  async function boot() {
    bindGlobal();
    try {
      await refresh();
      const slug = location.hash.replace(/^#\//, '');
      if (slug && state.skills.some((s) => s.slug === slug)) await openSkill(slug);
    } catch (error) { fail(error); }
  }

  boot();
})();
