(() => {
    ToolPrefs.fields('pdf.settings', ['pdfMode']);
    const $ = id => document.getElementById(id);
    pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/js/pdf.worker.min.js';
    let documents = [], pages = [], busy = false, nextId = 0, dragged = null;
    const message = (text, failed = false) => ToolUI.message($('pdfMessage'), text, failed);
    const previews = new Map();
    const observer = new IntersectionObserver(entries => {
        for (const entry of entries) if (entry.isIntersecting) {
            observer.unobserve(entry.target);
            thumbnail(entry.target, entry.target.pdfEntry);
        }
    }, {rootMargin: '200px'});
    async function thumbnail(card, entry) {
        const key = `${entry.document.id}/${entry.page}/${entry.rotation}`;
        try {
            let url = previews.get(key);
            if (!url) {
                const pdf = await entry.document.pdf;
                if (!pdf) throw new Error('無法預覽');
                const page = await pdf.getPage(entry.page + 1);
                const rotation = (page.rotate + entry.rotation) % 360;
                const original = page.getViewport({scale: 1, rotation});
                const viewport = page.getViewport({scale: Math.min(150 / original.width, 150 / original.height), rotation});
                const canvas = document.createElement('canvas');
                canvas.width = Math.ceil(viewport.width); canvas.height = Math.ceil(viewport.height);
                await page.render({canvasContext: canvas.getContext('2d'), viewport}).promise;
                url = canvas.toDataURL('image/png'); previews.set(key, url);
            }
            if (!card.isConnected) return;
            const image = document.createElement('img'); image.src = url; image.alt = `第 ${entry.page + 1} 頁預覽`;
            image.className = 'max-w-full max-h-full object-contain';
            card.querySelector('.pdf-thumb').replaceChildren(image);
        } catch (_) {
            if (card.isConnected) card.querySelector('.pdf-thumb').textContent = `第 ${entry.page + 1} 頁（無法預覽）`;
        }
    }
    function updateControls() {
        const selected = pages.filter(page => page.selected).length;
        $('pdfSummary').textContent = `${documents.length} 份文件 · 已選 ${selected} / ${pages.length} 頁`;
        $('pdfSettings').disabled = busy;
        $('pdfFiles').disabled = busy;
        $('processPdf').disabled = busy || !selected;
        for (const id of ['selectAllPdf', 'deselectAllPdf', 'clearPdf', 'applyPdfRange']) $(id).disabled = busy || !pages.length;
        $('pdfDocuments').querySelectorAll('button').forEach(button => button.disabled = busy);
        $('pdfPages').querySelectorAll('button,input').forEach(element => element.disabled = busy);
        $('pdfPages').querySelectorAll('.pdf-card').forEach(card => card.draggable = !busy);
    }
    function render() {
        observer.disconnect(); $('pdfPages').replaceChildren(); $('pdfDocuments').replaceChildren();
        documents.forEach(doc => {
            const row = document.createElement('div'); row.className = 'flex gap-3 items-center text-sm text-slate-400';
            const name = document.createElement('span'); name.className = 'flex-1 min-w-0 break-all';
            name.textContent = `${doc.file.name} · ${doc.count} 頁 · ${ToolUI.bytes(doc.file.size)}`;
            const remove = document.createElement('button'); remove.className = 'tool-secondary'; remove.textContent = '移除文件';
            remove.addEventListener('click', async () => {
                if (busy) return;
                documents = documents.filter(item => item !== doc); pages = pages.filter(item => item.document !== doc);
                for (const key of previews.keys()) if (key.startsWith(`${doc.id}/`)) previews.delete(key);
                doc.password = ''; (await doc.pdf)?.destroy(); render();
            });
            row.append(name, remove); $('pdfDocuments').append(row);
        });
        pages.forEach((entry, index) => {
            const card = document.createElement('div'); card.className = `pdf-card ${entry.selected ? '' : 'excluded'}`;
            card.pdfEntry = entry;
            card.innerHTML = '<div class="flex items-center justify-between mb-2"><label class="text-xs text-slate-300 flex gap-2"><input type="checkbox" class="accent-blue-500"><span></span></label><span class="text-xs text-slate-500"></span></div><div class="pdf-thumb text-xs text-slate-400">載入預覽…</div><p class="text-xs text-slate-400 truncate mb-2"></p><div class="flex justify-between gap-1"><button class="tool-secondary px-2" type="button" aria-label="向前移動">←</button><button class="tool-secondary px-2" type="button" aria-label="順時針旋轉 90 度">↻</button><button class="tool-secondary px-2" type="button" aria-label="向後移動">→</button></div>';
            card.querySelector('label span').textContent = `#${index + 1}`;
            card.querySelector('div > span').textContent = `${entry.rotation}°`;
            const title = `${entry.document.file.name} · 第 ${entry.page + 1} 頁`;
            card.querySelector('p').textContent = title; card.querySelector('p').title = title;
            const checkbox = card.querySelector('input'); checkbox.checked = entry.selected;
            checkbox.addEventListener('change', () => { entry.selected = checkbox.checked; card.classList.toggle('excluded', !entry.selected); updateControls(); });
            const buttons = card.querySelectorAll('button');
            buttons[0].addEventListener('click', () => move(index, index - 1));
            buttons[1].addEventListener('click', () => { entry.rotation = (entry.rotation + 90) % 360; render(); });
            buttons[2].addEventListener('click', () => move(index, index + 1));
            card.addEventListener('dragstart', event => {
                if (busy || event.target.closest('button,input')) { event.preventDefault(); return; }
                dragged = entry; event.dataTransfer.setData('text/plain', 'pdf-page'); event.dataTransfer.effectAllowed = 'move';
            });
            card.addEventListener('dragover', event => { if (dragged && !busy) { event.preventDefault(); card.classList.add('drag-target'); } });
            card.addEventListener('dragleave', () => card.classList.remove('drag-target'));
            card.addEventListener('drop', event => {
                if (!dragged || busy) return; event.preventDefault();
                move(pages.indexOf(dragged), pages.indexOf(entry)); dragged = null;
            });
            card.addEventListener('dragend', () => { dragged = null; document.querySelectorAll('.drag-target').forEach(el => el.classList.remove('drag-target')); });
            $('pdfPages').append(card); observer.observe(card);
        });
        updateControls();
    }
    function move(from, to) {
        if (busy || from < 0 || to < 0 || to >= pages.length || from === to) return;
        pages.splice(to, 0, pages.splice(from, 1)[0]); render();
    }
    async function askPassword(name) {
        const dialog = $('pdfPasswordDialog'); $('pdfPasswordName').textContent = name; $('pdfPassword').value = '';
        return new Promise(resolve => {
            const submit = event => { event.preventDefault(); close($('pdfPassword').value); };
            const cancel = () => close(null);
            function close(value) {
                $('pdfPasswordForm').removeEventListener('submit', submit);
                $('pdfPasswordCancel').removeEventListener('click', cancel);
                dialog.removeEventListener('cancel', cancel);
                $('pdfPassword').value = ''; dialog.close(); resolve(value);
            }
            $('pdfPasswordForm').addEventListener('submit', submit);
            $('pdfPasswordCancel').addEventListener('click', cancel); dialog.addEventListener('cancel', cancel);
            dialog.showModal(); $('pdfPassword').focus();
        });
    }
    async function info(file, password) {
        const data = new FormData(); data.append('file', file); data.append('password', password);
        const response = await fetch('/api/pdf-info', {method: 'POST', body: data});
        if (!response.ok) throw new Error(await ToolUI.error(response));
        return response.json();
    }
    async function add(files) {
        if (busy || !files.length) return;
        const valid = files.filter(file => /\.pdf$/i.test(file.name));
        const failures = valid.length !== files.length ? ['部分非 PDF 檔案已略過'] : [];
        if (documents.length + valid.length > 20 || documents.reduce((sum, doc) => sum + doc.file.size, 0) + valid.reduce((sum, file) => sum + file.size, 0) > 50 * 1024 * 1024) {
            message('最多 20 個檔案，合計不可超過 50 MB', true); return;
        }
        busy = true; updateControls();
        for (const file of valid) {
            message(`正在讀取 ${file.name}…`);
            try {
                let metadata, password = '';
                try { metadata = await info(file, password); }
                catch (error) {
                    if (!error.message.includes('密碼')) throw error;
                    password = await askPassword(file.name);
                    if (password === null) { failures.push(`${file.name} 已略過`); continue; }
                    metadata = await info(file, password);
                }
                if (pages.length + metadata.pages > 500) throw new Error('文件合計超過 500 頁，請減少文件');
                const buffer = await file.arrayBuffer();
                const pdf = pdfjsLib.getDocument({data: buffer, password, isEvalSupported: false}).promise.catch(() => null);
                const doc = {id: nextId++, file, password, count: metadata.pages, pdf};
                documents.push(doc);
                for (let page = 0; page < doc.count; page++) pages.push({document: doc, page, rotation: 0, selected: true});
                render();
            } catch (error) { failures.push(`${file.name}：${error.message}`); }
        }
        busy = false; render();
        message(failures.length ? failures.join('；') : `文件已加入，共 ${pages.length} 頁`, failures.length > 0);
    }
    ToolUI.upload($('pdfDrop'), $('pdfFiles'), add);
    $('selectAllPdf').addEventListener('click', () => { pages.forEach(page => page.selected = true); render(); });
    $('deselectAllPdf').addEventListener('click', () => { pages.forEach(page => page.selected = false); render(); });
    $('clearPdf').addEventListener('click', () => {
        for (const doc of documents) { doc.password = ''; doc.pdf.then(pdf => pdf?.destroy()); }
        documents = []; pages = []; previews.clear(); $('pdfRange').value = ''; message(''); render();
    });
    $('applyPdfRange').addEventListener('click', () => {
        const value = $('pdfRange').value.replace(/，/g, ',').trim(), order = [];
        try {
            if (!value) throw new Error('請輸入頁碼');
            for (const part of value.split(',')) {
                const match = part.trim().match(/^(\d+)(?:\s*-\s*(\d+))?$/);
                if (!match) throw new Error('頁碼格式請使用 1-3,6,5');
                const first = Number(match[1]), last = match[2] ? Number(match[2]) : first;
                if (Math.min(first, last) < 1 || Math.max(first, last) > pages.length) throw new Error(`頁碼必須介於 1 到 ${pages.length}`);
                const step = first <= last ? 1 : -1;
                for (let page = first; page !== last + step; page += step) {
                    if (order.includes(page - 1)) throw new Error('頁碼不能重複');
                    order.push(page - 1);
                }
            }
            const selected = order.map(index => pages[index]), rest = pages.filter((_, index) => !order.includes(index));
            selected.forEach(page => page.selected = true); rest.forEach(page => page.selected = false);
            pages = [...selected, ...rest]; $('pdfRange').value = ''; render(); message(`已選 ${selected.length} 頁並依輸入順序排列`);
        } catch (error) { message(error.message, true); }
    });
    $('processPdf').addEventListener('click', async () => {
        if (busy || !pages.some(page => page.selected)) return;
        const mode = $('pdfMode').value;
        const name = ToolUI.filename($('pdfName').value, '整理後文件').replace(/\.(pdf|zip)$/i, '') || '整理後文件';
        const data = new FormData();
        for (const doc of documents) data.append('files', doc.file);
        data.append('passwords', JSON.stringify(documents.map(doc => doc.password)));
        data.append('plan', JSON.stringify(pages.filter(page => page.selected).map(page => ({file: documents.indexOf(page.document), page: page.page, rotation: page.rotation}))));
        data.append('mode', mode); data.append('name', name);
        busy = true; updateControls(); message('正在整理 PDF…');
        try {
            const response = await fetch('/api/pdf-process', {method: 'POST', body: data});
            if (!response.ok) throw new Error(await ToolUI.error(response));
            ToolUI.download(await response.blob(), `${name}.${mode === 'split' ? 'zip' : 'pdf'}`);
            message('處理完成，已開始下載');
        } catch (error) { message(error.message, true); }
        finally { busy = false; updateControls(); }
    });
    render();
})();
