(() => {
    const $ = id => document.getElementById(id);
    let controller = null, previewURL = null, generation = 0;
    const message = (text, failed = false) => ToolUI.message($('qrScanMessage'), text, failed);
    function clear() {
        generation++; controller?.abort();
        if (previewURL) URL.revokeObjectURL(previewURL);
        previewURL = null; $('qrScanPreview').removeAttribute('src');
        $('qrScanPreview').classList.add('hidden'); $('qrScanResults').replaceChildren();
        $('qrScanName').textContent = ''; $('qrScanClear').disabled = true; message('');
    }
    async function scan(files) {
        if (!files.length) return;
        const file = files[0];
        if (!/\.(png|jpe?g|webp)$/i.test(file.name)) { message('只支援 PNG、JPG、WebP 圖片', true); return; }
        if (file.size > 50 * 1024 * 1024) { message('圖片不可超過 50 MB', true); return; }
        clear(); const current = generation;
        controller = new AbortController();
        previewURL = URL.createObjectURL(file); $('qrScanPreview').src = previewURL;
        $('qrScanPreview').classList.remove('hidden'); $('qrScanName').textContent = file.name;
        $('qrScanClear').disabled = false; message('正在辨識 QR Code…');
        const data = new FormData(); data.append('image', file);
        try {
            const response = await fetch('/api/qr-decode', {method: 'POST', body: data, signal: controller.signal});
            if (!response.ok) throw new Error(await ToolUI.error(response));
            const result = await response.json();
            if (current !== generation) return;
            message(result.success ? `找到 ${result.results.length} 個 QR Code${files.length > 1 ? '（本次讀取第一張圖片）' : ''}` : result.message, !result.success);
            result.results.forEach((value, index) => {
                const card = document.createElement('div'); card.className = 'qr-result';
                const label = document.createElement('p'); label.className = 'text-xs text-slate-500 mb-2'; label.textContent = `結果 ${index + 1}`;
                const content = document.createElement('pre'); content.textContent = value;
                const actions = document.createElement('div'); actions.className = 'flex flex-wrap gap-2 mt-3';
                const copy = document.createElement('button'); copy.className = 'tool-secondary'; copy.textContent = '複製內容';
                copy.addEventListener('click', async () => {
                    try { await navigator.clipboard.writeText(value); copy.textContent = '已複製'; }
                    catch (_) { message('複製失敗，請選取辨識結果後手動複製', true); }
                });
                actions.append(copy);
                try {
                    const url = new URL(value);
                    if (['http:', 'https:'].includes(url.protocol)) {
                        const link = document.createElement('a'); link.className = 'tool-secondary';
                        link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
                        link.textContent = `開啟 ${url.hostname}`; actions.append(link);
                    }
                } catch (_) { /* Plain QR content is displayed as text. */ }
                card.append(label, content, actions); $('qrScanResults').append(card);
            });
        } catch (error) { if (current === generation && error.name !== 'AbortError') message(error.message, true); }
    }
    ToolUI.upload($('qrScanDrop'), $('qrScanFile'), scan, true);
    $('qrScanClear').addEventListener('click', clear);
})();
