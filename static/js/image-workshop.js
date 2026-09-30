(() => {
    const $ = id => document.getElementById(id);
    const items = [];
    let busy = false, processing = false, controller = null;
    const message = (text, error = false) => ToolUI.message($('imageMessage'), text, error);
    function release(item) {
        if (item.originalURL) URL.revokeObjectURL(item.originalURL);
        if (item.outputURL) URL.revokeObjectURL(item.outputURL);
    }
    function render() {
        $('imageFiles').disabled = busy;
        $('imageSettings').disabled = busy;
        $('processImages').disabled = busy || !items.length;
        $('cancelImages').classList.toggle('hidden', !processing);
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
    ToolUI.upload($('imageDrop'), $('imageFiles'), add);
    $('imageQuality').addEventListener('input', () => $('imageQualityValue').textContent = $('imageQuality').value);
    $('imagePreset').addEventListener('change', () => {
        if ($('imagePreset').value !== 'custom') $('imageWidth').value = $('imageHeight').value = $('imagePreset').value;
    });
    for (const id of ['imageWidth', 'imageHeight']) $(id).addEventListener('input', () => $('imagePreset').value = 'custom');
    $('clearImages').addEventListener('click', () => { items.forEach(release); items.length = 0; message(''); render(); });
    $('cancelImages').addEventListener('click', () => controller?.abort());
    $('processImages').addEventListener('click', async () => {
        if (busy || !items.length) return;
        if (!['imageWidth', 'imageHeight'].every(id => $(id).checkValidity() && $(id).value !== '' && Number.isInteger(Number($(id).value)))) {
            message('寬度與高度請填 0 到 10000 的整數', true); return;
        }
        const settings = {format: $('imageFormat').value, quality: $('imageQuality').value,
            max_width: $('imageWidth').value, max_height: $('imageHeight').value,
            background: $('imageBackground').value, keep_metadata: $('imageMetadata').checked ? '1' : '0'};
        controller = new AbortController(); busy = true; processing = true;
        let cancelled = false;
        for (const item of items) {
            if (item.outputURL) URL.revokeObjectURL(item.outputURL);
            item.output = item.outputURL = null; item.error = ''; item.status = '等待處理';
        }
        for (let index = 0; index < items.length; index++) {
            const item = items[index];
            item.status = '處理中…';
            render(); message(`正在處理第 ${index + 1} / ${items.length} 張…`);
            const data = new FormData(); data.append('image', item.file);
            Object.entries(settings).forEach(([key, value]) => data.append(key, value));
            try {
                const response = await fetch('/api/image-process', {method: 'POST', body: data, signal: controller.signal});
                if (!response.ok) throw new Error(await ToolUI.error(response));
                item.output = await response.blob(); item.outputURL = URL.createObjectURL(item.output);
                item.width = response.headers.get('X-Image-Width'); item.height = response.headers.get('X-Image-Height');
                const ext = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}[item.output.type];
                item.name = `${ToolUI.filename(item.file.name).replace(/\.[^.]+$/, '')}_processed.${ext}`;
            } catch (error) {
                if (error.name === 'AbortError') { item.status = '已停止'; cancelled = true; break; }
                item.error = error.message;
            }
        }
        busy = false; processing = false; render();
        const ready = items.filter(item => item.output).length;
        message(`${cancelled ? '已停止' : '處理完成'}，${ready} / ${items.length} 張可下載`, ready === 0);
    });
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
