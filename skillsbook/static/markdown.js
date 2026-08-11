/* Tiny markdown renderer — enough for SKILL.md bodies, zero dependencies.
   Everything is escaped first, so raw HTML in a skill is shown, never run. */
(function (global) {
  'use strict';

  function esc(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function safeUrl(url) {
    const trimmed = String(url).trim();
    return /^(https?:|mailto:|#|\/|\.\/|\.\.\/)/i.test(trimmed) || !/:/.test(trimmed)
      ? trimmed
      : '#';
  }

  function inline(text) {
    let out = esc(text);
    const codes = [];
    out = out.replace(/`([^`]+)`/g, (_, code) => `@@SBCODE${codes.push(code) - 1}@@`);
    out = out.replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g,
      (_, alt, src) => `<img src="${esc(safeUrl(src))}" alt="${alt}">`);
    out = out.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g,
      (_, label, href) => `<a href="${esc(safeUrl(href))}" target="_blank" rel="noopener">${label}</a>`);
    out = out.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g,
      (_, lead, url) => `${lead}<a href="${esc(url)}" target="_blank" rel="noopener">${url}</a>`);
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
    out = out.replace(/~~([^~]+)~~/g, '<del>$1</del>');
    out = out.replace(/@@SBCODE(\d+)@@/g, (_, index) => `<code>${codes[index]}</code>`);
    return out;
  }

  function listBlock(lines, start) {
    const bullet = /^(\s*)([-*+]|\d+\.)\s+(.*)$/;
    const items = [];
    let index = start;
    const first = lines[index].match(bullet);
    const ordered = /\d/.test(first[2]);
    const baseIndent = first[1].length;

    while (index < lines.length) {
      const match = lines[index].match(bullet);
      if (match && match[1].length >= baseIndent) {
        if (match[1].length > baseIndent) {
          const nested = listBlock(lines, index);
          if (items.length) items[items.length - 1] += nested.html;
          index = nested.next;
          continue;
        }
        if (/\d/.test(match[2]) !== ordered) break;
        items.push(inline(match[3]));
        index += 1;
        continue;
      }
      if (lines[index].trim() === '' && lines[index + 1] && bullet.test(lines[index + 1])) {
        index += 1;
        continue;
      }
      break;
    }
    const tag = ordered ? 'ol' : 'ul';
    const html = `<${tag}>${items.map((item) => `<li>${item}</li>`).join('')}</${tag}>`;
    return { html, next: index };
  }

  function tableBlock(lines, start) {
    const rows = [];
    let index = start;
    while (index < lines.length && /\|/.test(lines[index]) && lines[index].trim()) {
      rows.push(lines[index]);
      index += 1;
    }
    if (rows.length < 2 || !/^[\s|:-]+$/.test(rows[1])) return null;
    const cells = (line) => line.replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim());
    const head = cells(rows[0]).map((cell) => `<th>${inline(cell)}</th>`).join('');
    const body = rows.slice(2)
      .map((row) => `<tr>${cells(row).map((cell) => `<td>${inline(cell)}</td>`).join('')}</tr>`)
      .join('');
    return { html: `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`, next: index };
  }

  function render(source) {
    const lines = String(source || '').replace(/\r\n?/g, '\n').split('\n');
    const out = [];
    let index = 0;

    while (index < lines.length) {
      const line = lines[index];

      if (/^\s*```/.test(line)) {
        const lang = line.replace(/^\s*```/, '').trim();
        const buffer = [];
        index += 1;
        while (index < lines.length && !/^\s*```/.test(lines[index])) {
          buffer.push(lines[index]);
          index += 1;
        }
        index += 1;
        const cls = lang ? ` class="lang-${esc(lang.split(/\s+/)[0])}"` : '';
        out.push(`<pre><code${cls}>${esc(buffer.join('\n'))}</code></pre>`);
        continue;
      }

      if (!line.trim()) { index += 1; continue; }

      const heading = line.match(/^(#{1,6})\s+(.*)$/);
      if (heading) {
        const level = Math.min(heading[1].length, 6);
        out.push(`<h${level}>${inline(heading[2].replace(/\s+#+\s*$/, ''))}</h${level}>`);
        index += 1;
        continue;
      }

      if (/^\s{0,3}([-*_])\s*\1\s*\1[-*_\s]*$/.test(line)) {
        out.push('<hr>');
        index += 1;
        continue;
      }

      if (/^\s*>/.test(line)) {
        const buffer = [];
        while (index < lines.length && /^\s*>/.test(lines[index])) {
          buffer.push(lines[index].replace(/^\s*>\s?/, ''));
          index += 1;
        }
        out.push(`<blockquote>${render(buffer.join('\n'))}</blockquote>`);
        continue;
      }

      if (/\|/.test(line) && lines[index + 1] && /^[\s|:-]+$/.test(lines[index + 1])) {
        const table = tableBlock(lines, index);
        if (table) { out.push(table.html); index = table.next; continue; }
      }

      if (/^(\s*)([-*+]|\d+\.)\s+/.test(line)) {
        const list = listBlock(lines, index);
        out.push(list.html);
        index = list.next;
        continue;
      }

      const buffer = [];
      while (
        index < lines.length && lines[index].trim() &&
        !/^\s*(```|#{1,6}\s|>)/.test(lines[index]) &&
        !/^(\s*)([-*+]|\d+\.)\s+/.test(lines[index])
      ) {
        buffer.push(lines[index]);
        index += 1;
      }
      if (buffer.length) out.push(`<p>${inline(buffer.join('\n'))}</p>`);
    }

    return out.join('\n');
  }

  global.md = { render, esc, inline };
})(window);
