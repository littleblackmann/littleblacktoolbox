(() => {
    const $ = id => document.getElementById(id);
    const items = [];
    let busy = false, processing = false, controller = null;
    const message = (text, error = false) => ToolUI.message($('imageMessage'), text, error);
    const fieldIds = ['imageFormat', 'imagePreset', 'imageWidth', 'imageHeight', 'imageQuality', 'imageBackground', 'imageMetadata', 'imageRemoveBg'];
    const saveSettings = ToolPrefs.fields('image.settings', fieldIds);
    let recipes = ToolPrefs.read('image.recipes', []).filter(recipe => typeof recipe?.name === 'string' && recipe.settings && typeof recipe.settings === 'object').slice(0, 10);
    function settings() { return Object.fromEntries(fieldIds.map(id => [id, $(id).type === 'checkbox' ? $(id).checked : $(id).value])); }
    function applySettings(values) { for (const id of fieldIds) if (Object.hasOwn(values, id)) { if ($(id).type === 'checkbox') $(id).checked = Boolean(values[id]); else { const before = $(id).value; $(id).value = values[id]; if (!$(id).checkValidity() || !$(id).value) $(id).value = before; } } $('imageQualityValue').textContent = $('imageQuality').value; saveSettings(); }
    function listRecipes() { $('imageRecipe').querySelectorAll('option[data-saved]').forEach(option => option.remove()); recipes.forEach((recipe, index) => { const option = document.createElement('option'); option.value = `saved:${index}`; option.dataset.saved = 'true'; option.textContent = recipe.name; $('imageRecipe').append(option); }); }
    function preset(key) { if (['share', 'transparent'].includes(key)) applySettings({imageFormat: 'WEBP', imagePreset: '1280', imageWidth: '1280', imageHeight: '1280', imageQuality: '85', imageMetadata: false, imageRemoveBg: key === 'transparent'}); else if (key.startsWith('saved:') && recipes[Number(key.slice(6))]) applySettings(recipes[Number(key.slice(6))].settings); }
    listRecipes(); $('imageQualityValue').textContent = $('imageQuality').value;
    const requestedPreset = new URLSearchParams(location.search).get('preset');
    if (['share', 'transparent'].includes(requestedPreset)) { $('imageRecipe').value = requestedPreset; preset(requestedPreset); }
    $('imageRecipe').addEventListener('change', () => preset($('imageRecipe').value));
    fieldIds.forEach(id => $(id).addEventListener('input', () => { $('imageRecipe').value = 'custom'; if (items.some(item => item.output)) message('設定已變更，請重新處理圖片以套用'); }));
    $('saveImageRecipe').addEventListener('click', () => { const name = $('imageRecipeName').value.trim(); if (!name) { message('請輸入流程名稱', true); return; } recipes = recipes.filter(recipe => recipe.name !== name); recipes.unshift({name, settings: settings()}); recipes = recipes.slice(0, 10); if (!ToolPrefs.write('image.recipes', recipes)) { message('瀏覽器無法儲存設定，請確認未停用本機儲存', true); return; } listRecipes(); $('imageRecipe').value = 'saved:0'; message(`已儲存「${name}」，下次可直接套用`); });
    function release(item) {
        if (item.originalURL) URL.revokeObjectURL(item.originalURL);
        if (item.outputURL) URL.revokeObjectURL(item.outputURL);
    }
    function render() {
        $('imageFiles').disabled = busy;
        $('imageSettings').disabled = busy;
        $('processImages').disabled = busy || !items.length;
        $('cancelImages').classList.toggle('hidden', !processing);
        $('retryImages').classList.toggle('hidden', !items.some(item => item.error));
        $('retryImages').disabled = busy;
        $('imageProgress').classList.toggle('hidden', !processing);
        $('clearImages').disabled = busy || !items.length;
        $('zipImages').disabled = busy || !items.some(item => item.output);
        const ready = items.filter(item => item.output).length;
        $('imageSummary').textContent = items.length ? `${items.length} 張 · ${ToolUI.bytes(items.reduce((sum, item) => sum + item.file.size, 0))} · 已完成 ${ready} 張` : '尚未選擇圖片';
        $('imageList').replaceChildren();
        items.forEach((item, index) => {
            const row = document.createElement('div');
            row.className = 'image-row flex gap-3 items-start';
            row.innerHTML = '<div class="image-thumbs"><img class="checkerboard" alt="原圖"><img class="checkerboard hidden" alt="處理結果"></div><div class="flex-1 min-w-0"><p class="text-sm text-slate-200 break-all"></p><p class="text-xs text-slate-500 mt-1"></p><p class="text-xs mt-2"></p><div class="flex gap-2 mt-3"></div></div>';
            const imgs = row.querySelectorAll('img');
            imgs.forEach(image => image.loading = 'lazy');
            imgs[0].src = item.originalURL;
            if (item.outputURL) { imgs[1].src = item.outputURL; imgs[1].classList.remove('hidden'); }
            const texts = row.querySelectorAll('p');
            texts[0].textContent = item.file.name;
            texts[1].textContent = `原檔 ${ToolUI.bytes(item.file.size)}`;
            texts[2].className = `text-xs mt-2 ${item.error ? 'text-red-400' : 'text-emerald-400'}`;
            if (item.output) {
                const percent = (1 - item.output.size / Math.max(1, item.file.size)) * 100;
                texts[2].textContent = `${item.width} × ${item.height} · ${ToolUI.bytes(item.output.size)} · ${percent >= 0 ? '減少' : '增加'} ${Math.abs(percent).toFixed(1)}%`;
                const download = document.createElement('button');
                download.className = 'tool-secondary'; download.textContent = '下載這張';
                download.addEventListener('click', () => ToolUI.download(item.output, item.name));
                row.querySelector('div.flex.gap-2').append(download);
            } else texts[2].textContent = item.error || item.status || '等待處理';
            if (item.error) { const retry = document.createElement('button'); retry.className = 'tool-secondary'; retry.textContent = '重試'; retry.disabled = busy; retry.addEventListener('click', () => process([item])); row.querySelector('div.flex.gap-2').append(retry); }
            const remove = document.createElement('button');
            remove.className = 'tool-secondary'; remove.textContent = '移除'; remove.disabled = busy;
            remove.addEventListener('click', () => { release(item); items.splice(index, 1); render(); });
            row.querySelector('div.flex.gap-2').append(remove);
            $('imageList').append(row);
        });
    }
    function add(files) {
        if (busy) return;
        const valid = files.filter(file => /\.(png|jpe?g|webp)$/i.test(file.name));
        if (valid.length !== files.length) message('部分檔案不是 PNG、JPG 或 WebP，已略過', true);
        if (items.length + valid.length > 50 || items.reduce((sum, item) => sum + item.file.size, 0) + valid.reduce((sum, file) => sum + file.size, 0) > 50 * 1024 * 1024) {
            message('最多 50 張圖片，合計不可超過 50 MB', true); return;
        }
        valid.forEach(file => items.push({file, originalURL: URL.createObjectURL(file)}));
        render();
    }
    ToolUI.upload($('imageDrop'), $('imageFiles'), add, true);
    $('imageQuality').addEventListener('input', () => $('imageQualityValue').textContent = $('imageQuality').value);
    $('imagePreset').addEventListener('change', () => {
        if ($('imagePreset').value !== 'custom') $('imageWidth').value = $('imageHeight').value = $('imagePreset').value;
        saveSettings();
    });
    for (const id of ['imageWidth', 'imageHeight']) $(id).addEventListener('input', () => $('imagePreset').value = 'custom');
    $('clearImages').addEventListener('click', () => { items.forEach(release); items.length = 0; message(''); render(); });
    $('cancelImages').addEventListener('click', () => controller?.abort());
    async function process(targets) {
        if (busy || !items.length) return;
        if (!['imageWidth', 'imageHeight'].every(id => $(id).checkValidity() && $(id).value !== '' && Number.isInteger(Number($(id).value)))) {
            message('寬度與高度請填 0 到 10000 的整數', true); return;
        }
        const options = {format: $('imageFormat').value, quality: $('imageQuality').value,
            max_width: $('imageWidth').value, max_height: $('imageHeight').value,
            background: $('imageBackground').value, keep_metadata: $('imageMetadata').checked ? '1' : '0'};
        controller = new AbortController(); busy = true; processing = true;
        let cancelled = false;
        saveSettings(); $('imageProgress').max = targets.length; $('imageProgress').value = 0;
        for (const item of targets) {
            if (item.outputURL) URL.revokeObjectURL(item.outputURL);
            item.output = item.outputURL = null; item.error = ''; item.status = '等待處理';
        }
        for (let index = 0; index < targets.length; index++) {
            const item = targets[index];
            item.status = '處理中…';
            render(); message(`正在處理第 ${index + 1} / ${targets.length} 張…`);
            const data = new FormData(); data.append('image', item.file);
            Object.entries(options).forEach(([key, value]) => data.append(key, value));
            try {
                if ($('imageRemoveBg').checked) { item.status = 'AI 去背中…'; render(); const bgData = new FormData(); bgData.append('image', item.file); const bg = await fetch('/api/remove-bg', {method: 'POST', body: bgData, signal: controller.signal}); if (!bg.ok) throw new Error(await ToolUI.error(bg)); const value = await bg.json(); const removed = await (await fetch(value.image, {signal: controller.signal})).blob(); data.set('image', removed, 'removed.png'); item.status = '縮圖與轉檔中…'; render(); }
                const response = await fetch('/api/image-process', {method: 'POST', body: data, signal: controller.signal});
                if (!response.ok) throw new Error(await ToolUI.error(response));
                item.output = await response.blob(); item.outputURL = URL.createObjectURL(item.output);
                item.width = response.headers.get('X-Image-Width'); item.height = response.headers.get('X-Image-Height');
                const ext = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}[item.output.type];
                item.name = `${ToolUI.filename(item.file.name).replace(/\.[^.]+$/, '')}_processed.${ext}`;
                $('imageProgress').value = index + 1;
            } catch (error) {
                if (error.name === 'AbortError') { item.status = '已停止'; cancelled = true; break; }
                item.error = ToolUI.failure(error);
            }
        }
        busy = false; processing = false; render();
        const ready = items.filter(item => item.output).length;
        message(`${cancelled ? '已停止' : '處理完成'}，${ready} / ${items.length} 張可下載`, ready === 0);
    }
    $('processImages').addEventListener('click', () => process(items));
    $('retryImages').addEventListener('click', () => process(items.filter(item => item.error)));
    $('zipImages').addEventListener('click', async () => {
        busy = true; render(); message('正在準備 ZIP…');
        try {
            const zip = new JSZip(), names = new Set();
            for (const item of items.filter(item => item.output)) {
                let name = item.name, index = 2;
                while (names.has(name.toLowerCase())) name = item.name.replace(/(\.[^.]+)$/, `_${index++}$1`);
                names.add(name.toLowerCase()); zip.file(name, item.output);
            }
            const blob = await zip.generateAsync({type: 'blob', compression: 'STORE'});
            ToolUI.download(blob, '圖片批次處理.zip'); message('ZIP 已開始下載');
        } catch (error) { message(`ZIP 產生失敗：${error.message}`, true); }
        finally { busy = false; render(); }
    });
    render();
})();
