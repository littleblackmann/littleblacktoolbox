/* Shared local file tools UI. */
window.ToolUI = {
    bytes(value) {
        if (value < 1024) return `${value} B`;
        if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
        return `${(value / 1024 / 1024).toFixed(2)} MB`;
    },
    download(blob, name) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = name;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    filename(name, fallback = '檔案') {
        return (name.split(/[\\/]/).pop().replace(/[\x00-\x1f<>:"|?*]/g, '_').replace(/[ .]+$/g, '').slice(0, 120) || fallback);
    },
    async error(response) {
        try { return (await response.json()).error || '處理失敗，請稍後再試'; }
        catch (_) { return '伺服器沒有回應，請確認工具箱仍在執行'; }
    },
    message(element, value, failed = false) {
        element.textContent = value;
        element.className = `tool-message ${failed ? 'text-red-400' : 'text-slate-400'}`;
    },
    upload(zone, input, handler, paste = false) {
        zone.addEventListener('click', () => { if (!input.disabled) input.click(); });
        zone.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                if (!input.disabled) input.click();
            }
        });
        input.addEventListener('change', () => { handler([...input.files]); input.value = ''; });
        for (const type of ['dragenter', 'dragover']) zone.addEventListener(type, event => {
            event.preventDefault();
            if (!input.disabled) zone.classList.add('drag-active');
        });
        for (const type of ['dragleave', 'drop']) zone.addEventListener(type, event => {
            event.preventDefault(); zone.classList.remove('drag-active');
        });
        zone.addEventListener('drop', event => { if (!input.disabled) handler([...event.dataTransfer.files]); });
        if (paste) document.addEventListener('paste', event => {
            if (input.disabled || !event.clipboardData.files.length) return;
            const images = [...event.clipboardData.files].filter(file => file.type.startsWith('image/'));
            if (images.length) { event.preventDefault(); handler(images); }
        });
    }
};
