(() => {
    const $ = id => document.getElementById(id);
    let files = [], selected = new Set(), folder = '', preview = null, busy = false;
    const message = (text, failed = false) => ToolUI.message($('renameMessage'), text, failed);
    const ids = ['renameMode', 'renameBase', 'renameStart', 'renameDigits', 'renameDate', 'renamePrefix', 'renameSuffix', 'renameFind', 'renameReplace'];
    const save = ToolPrefs.fields('rename.settings', ids);
    async function api(path, value) {
        const response = await fetch(`/api/rename/${path}`, {method: value === undefined ? 'GET' : 'POST', headers: {'Content-Type': 'application/json', 'X-Toolbox-Token': document.querySelector('meta[name="toolbox-token"]').content}, body: value === undefined ? undefined : JSON.stringify(value)});
        if (!response.ok) throw new Error(await ToolUI.error(response));
        return response.json();
    }
    function invalidate() { preview = null; render(); }
    function options() { return {mode: $('renameMode').value, base: $('renameBase').value, start: Number($('renameStart').value), digits: Number($('renameDigits').value), date: $('renameDate').value, prefix: $('renamePrefix').value, suffix: $('renameSuffix').value, find: $('renameFind').value, replace: $('renameReplace').value}; }
    function mode() { $('renameKeep').classList.toggle('hidden', $('renameMode').value === 'sequence'); $('renameSequence').classList.toggle('hidden', $('renameMode').value !== 'sequence'); }
    function render() {
        $('renameRows').replaceChildren();
        const filter = $('renameFilter').value.toLocaleLowerCase();
        const visible = files.filter(file => file.name.toLocaleLowerCase().includes(filter));
        const changes = new Map((preview?.entries || []).map(entry => [entry.old, entry.new]));
        for (const file of visible) {
            const row = document.createElement('tr'), cell = document.createElement('td');
            const input = document.createElement('input'); input.type = 'checkbox'; input.checked = selected.has(file.name); input.disabled = busy; input.setAttribute('aria-label', `選取 ${file.name}`);
            input.addEventListener('change', () => { input.checked ? selected.add(file.name) : selected.delete(file.name); invalidate(); }); cell.append(input); row.append(cell);
            for (const text of [file.name, changes.get(file.name) || '—']) { const td = document.createElement('td'); td.textContent = text; row.append(td); }
            if (changes.has(file.name) && changes.get(file.name) !== file.name) row.lastChild.className = 'text-blue-300';
            $('renameRows').append(row);
        }
        $('renameSummary').textContent = `${files.length} 個檔案 · 選取 ${selected.size} 個${preview ? ` · 將改名 ${preview.changed} 個` : ''}`;
        $('renameEmpty').hidden = visible.length > 0;
        $('renameEmpty').textContent = files.length ? '沒有符合篩選的檔案。' : '資料夾沒有可改名的檔案。';
        $('previewRename').disabled = busy || !selected.size;
        $('applyRename').disabled = busy || !preview?.changed;
        $('applyRename').textContent = preview?.changed ? `執行改名（${preview.changed} 個檔案）` : '執行改名';
        $('renameSettings').disabled = busy;
        for (const id of ['renameFolder', 'chooseRenameFolder', 'loadRenameFolder', 'renameSelectAll', 'renameSelectNone', 'renameFilter']) $(id).disabled = busy;
        $('renameHistory').querySelectorAll('button').forEach(button => button.disabled = busy);
    }
    async function history() {
        try {
            const data = await api('history'); $('renameHistory').replaceChildren();
            if (!data.records.length) $('renameHistory').textContent = '目前沒有改名紀錄。';
            for (const record of data.records) {
                const row = document.createElement('div'); row.className = 'flex flex-wrap items-center gap-3 border-t border-slate-700 pt-3';
                const text = document.createElement('p'); text.className = 'flex-1 min-w-0 text-sm text-slate-300 break-all';
                const status = {completed: '可復原', undone: '已復原', 'rolled-back': '未完成，已還原', running: '操作中斷，需復原', 'needs-recovery': '需檢查復原紀錄'}[record.status] || record.status;
                text.textContent = `${record.created.replace('T', ' ')} · ${record.count} 個 · ${status}\n${record.folder}`; text.style.whiteSpace = 'pre-line'; row.append(text);
                if (record.status === 'completed') {
                    const button = document.createElement('button'); button.className = 'tool-secondary'; button.textContent = '復原這次改名';
                    button.addEventListener('click', () => work(async () => { const result = await api('undo', {id: record.id}); message(`已復原 ${result.count} 個檔案`); if (folder === result.folder) await load(); await history(); })); row.append(button);
                }
                if (['running', 'needs-recovery'].includes(record.status)) { const button = document.createElement('button'); button.className = 'tool-secondary'; button.textContent = '復原中斷操作'; button.addEventListener('click', () => work(async () => { const result = await api('recover', {id: record.id}); if (folder === result.folder) await load(); await history(); message(`已復原中斷操作，共 ${result.count} 個檔案`); })); row.append(button); }
                $('renameHistory').append(row);
            }
        } catch (error) { message(ToolUI.failure(error), true); }
    }
    async function work(action) { if (busy) return; busy = true; render(); try { await action(); } catch (error) { preview = null; message(ToolUI.failure(error), true); } finally { busy = false; render(); } }
    async function load() { const result = await api('list', {folder: $('renameFolder').value}); folder = result.folder; $('renameFolder').value = folder; files = result.files; selected = new Set(files.map(file => file.name)); preview = null; render(); }
    $('loadRenameFolder').addEventListener('click', () => work(async () => { await load(); message(`已讀取 ${files.length} 個檔案，請設定規則並預覽`); }));
    $('chooseRenameFolder').addEventListener('click', () => work(async () => { const result = await api('choose-folder', {}); if (result.folder) { $('renameFolder').value = result.folder; await load(); message(`已讀取 ${files.length} 個檔案`); } }));
    $('previewRename').addEventListener('click', () => work(async () => { if (!ids.every(id => $(id).checkValidity())) throw new Error('請檢查命名設定'); preview = await api('preview', {folder, names: [...selected], options: options()}); save(); message(preview.changed ? '請核對右側新檔名，再按執行改名' : '目前規則不會改變檔名'); }));
    $('applyRename').addEventListener('click', () => work(async () => { const result = await api('apply', {token: preview.token}); await load(); await history(); message(`已改名 ${result.count} 個檔案，可在下方復原`); }));
    $('renameFolder').addEventListener('input', () => { files = []; selected.clear(); folder = ''; invalidate(); });
    $('renameFilter').addEventListener('input', render);
    $('renameSelectAll').addEventListener('click', () => { files.filter(file => file.name.toLocaleLowerCase().includes($('renameFilter').value.toLocaleLowerCase())).forEach(file => selected.add(file.name)); invalidate(); });
    $('renameSelectNone').addEventListener('click', () => { selected.clear(); invalidate(); });
    ids.forEach(id => $(id).addEventListener('input', () => { mode(); invalidate(); }));
    mode(); render(); history();
})();
