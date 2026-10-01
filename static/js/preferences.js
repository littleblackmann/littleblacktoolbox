/* Settings only: no image bytes, document contents or folder paths are stored here. */
window.ToolPrefs = {
    read(key, fallback) {
        try { const value = JSON.parse(localStorage.getItem(`toolbox.${key}`)); if (value == null || (Array.isArray(fallback) && !Array.isArray(value)) || (fallback && typeof fallback === 'object' && !Array.isArray(fallback) && (typeof value !== 'object' || Array.isArray(value)))) return fallback; return value; }
        catch (_) { return fallback; }
    },
    write(key, value) {
        try { localStorage.setItem(`toolbox.${key}`, JSON.stringify(value)); return true; }
        catch (_) { return false; }
    },
    fields(key, ids) {
        const saved = this.read(key, {});
        const controls = ids.map(id => document.getElementById(id)).filter(Boolean);
        for (const field of controls) {
            if (!Object.hasOwn(saved, field.id)) continue;
            if (field.type === 'checkbox' && typeof saved[field.id] === 'boolean') field.checked = saved[field.id];
            else if (typeof saved[field.id] === 'string') {
                const before = field.value; field.value = saved[field.id];
                if (!field.value || !field.checkValidity()) field.value = before;
            }
        }
        const store = () => this.write(key, Object.fromEntries(controls.map(field => [field.id, field.type === 'checkbox' ? field.checked : field.value])));
        controls.forEach(field => field.addEventListener('change', store));
        return store;
    }
};
(() => {
    const path = location.pathname;
    const entry = (window.ToolCatalog || []).find(tool => tool.path === path);
    if (entry) ToolPrefs.write('recent', [entry.id, ...ToolPrefs.read('recent', []).filter(id => id !== entry.id)].slice(0, 6));
})();
