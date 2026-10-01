(() => {
    const dialog = document.getElementById('toolSearchDialog'), input = document.getElementById('toolSearchInput'), results = document.getElementById('toolSearchResults');
    let active = 0;
    function render() {
        const query = input.value.trim().toLocaleLowerCase();
        const tools = ToolCatalog.filter(tool => `${tool.name} ${tool.description} ${tool.keywords}`.toLocaleLowerCase().includes(query));
        results.replaceChildren(); active = 0;
        for (const tool of tools) {
            const link = document.createElement('a'); link.href = tool.path; link.className = 'search-result';
            const icon = document.createElement('i'); icon.dataset.lucide = tool.icon; icon.className = 'w-5 h-5 text-blue-300';
            const text = document.createElement('span'); text.textContent = tool.name; link.append(icon, text); results.append(link);
        }
        if (!tools.length) { const hint = document.createElement('p'); hint.className = 'text-sm text-slate-400 p-3'; hint.textContent = '找不到工具，試試「圖片」「文字」或「PDF」。'; results.append(hint); }
        lucide.createIcons(); highlight();
    }
    function highlight() { [...results.querySelectorAll('a')].forEach((link, index) => link.dataset.active = String(index === active)); }
    function open() { input.value = ''; render(); if (!dialog.open) dialog.showModal(); input.focus(); }
    document.getElementById('openToolSearch').addEventListener('click', open);
    document.getElementById('closeToolSearch').addEventListener('click', () => dialog.close());
    input.addEventListener('input', render);
    input.addEventListener('keydown', event => {
        const links = [...results.querySelectorAll('a')]; if (!links.length) return;
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); active = (active + (event.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length; highlight(); links[active].scrollIntoView({block: 'nearest'}); }
        if (event.key === 'Enter') { event.preventDefault(); location.href = links[active].href; }
    });
    document.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); dialog.open ? dialog.close() : open(); } });
})();
