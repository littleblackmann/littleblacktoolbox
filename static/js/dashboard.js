(() => {
    const $ = id => document.getElementById(id);
    let category = '全部';
    let favorites = new Set(ToolPrefs.read('favorites', []).filter(id => ToolCatalog.some(tool => tool.id === id)));
    function render() {
        const query = $('dashboardSearch').value.trim().toLocaleLowerCase();
        const tools = ToolCatalog.filter(tool => (category === '全部' || category === tool.category || (category === '收藏' && favorites.has(tool.id))) && `${tool.name} ${tool.description} ${tool.keywords}`.toLocaleLowerCase().includes(query));
        $('toolGrid').replaceChildren();
        for (const tool of tools) {
            const card = document.createElement('article'); card.className = 'catalog-card';
            const symbol = document.createElement('div'); symbol.className = `tool-symbol tool-color-${tool.color}`;
            const icon = document.createElement('i'); icon.dataset.lucide = tool.icon; symbol.append(icon);
            const star = document.createElement('button'); star.className = 'favorite-button'; star.setAttribute('aria-pressed', String(favorites.has(tool.id))); star.setAttribute('aria-label', `${favorites.has(tool.id) ? '取消收藏' : '收藏'}${tool.name}`);
            const starIcon = document.createElement('i'); starIcon.dataset.lucide = 'star'; starIcon.className = 'w-4 h-4'; star.append(starIcon);
            star.addEventListener('click', () => { favorites.has(tool.id) ? favorites.delete(tool.id) : favorites.add(tool.id); ToolPrefs.write('favorites', [...favorites]); render(); });
            const heading = document.createElement('h3'), link = document.createElement('a'); link.href = tool.path; link.className = 'card-link'; link.textContent = tool.name; heading.append(link);
            const description = document.createElement('p'); description.className = 'text-sm text-slate-400 mt-2 leading-relaxed'; description.textContent = tool.description;
            card.append(symbol, star, heading, description); $('toolGrid').append(card);
        }
        $('catalogTitle').textContent = `${category === '全部' ? '全部工具' : category}${query ? ' · 搜尋結果' : ''}`;
        $('catalogCount').textContent = `${tools.length} 個工具`;
        $('catalogEmpty').classList.toggle('hidden', tools.length > 0);
        $('catalogEmptyText').textContent = category === '收藏' && !favorites.size ? '還沒有收藏，按工具卡片上的星號就能加入。' : '找不到符合條件的工具，試試其他關鍵字。';
        $('categoryFilters').querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.category === category)));
        lucide.createIcons();
    }
    for (const id of ToolPrefs.read('recent', [])) {
        const tool = ToolCatalog.find(entry => entry.id === id); if (!tool) continue;
        const link = document.createElement('a'); link.href = tool.path; link.className = 'quick-link'; link.textContent = tool.name; $('recentTools').append(link);
    }
    $('recentSection').classList.toggle('hidden', !$('recentTools').children.length);
    $('dashboardSearch').addEventListener('input', render);
    $('categoryFilters').querySelectorAll('button').forEach(button => button.addEventListener('click', () => { category = button.dataset.category; render(); }));
    $('resetCatalog').addEventListener('click', () => { category = '全部'; $('dashboardSearch').value = ''; render(); });
    render();
})();
