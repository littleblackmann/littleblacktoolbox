(() => {
    const $ = id => document.getElementById(id), canvas = $('editorCanvas'), context = canvas.getContext('2d');
    let source = null, state = null, tool = 'arrow', drag = null, busy = false, generation = 0, frame = null;
    const undo = [], redo = [];
    const message = (value, failed = false) => ToolUI.message($('editorMessage'), value, failed);
    ToolPrefs.fields('editor.settings', ['editorColor', 'editorWidth', 'editorTextSize', 'editorFormat']);
    const hints = {arrow: '拖曳繪製箭頭，起點指向終點。', rect: '拖曳框選需要強調的範圍。', pen: '按住滑鼠或手指，自由繪製線條。', text: '先輸入說明文字，再點擊圖片放置。', mosaic: '拖曳選取要像素化的範圍。敏感文字建議使用實色遮蔽。', cover: '拖曳選取範圍，以所選顏色完全遮蔽。', crop: '拖曳保留範圍，放開後裁切；可按復原回到裁切前。'};
    function controls() {
        $('editorSettings').disabled = busy || !source;
        $('editorUndo').disabled = busy || !undo.length;
        $('editorRedo').disabled = busy || !redo.length;
        $('editorDownload').disabled = $('editorCopy').disabled = busy || !source;
        $('editorFile').disabled = busy;
        $('editorHint').textContent = hints[tool];
        $('editorTools').querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.tool === tool)));
    }
    function checkpoint() { undo.push(structuredClone(state)); if (undo.length > 100) undo.shift(); redo.length = 0; }
    function bounds(mark) {
        const x = Math.max(0, Math.min(canvas.width, Math.min(mark.a.x, mark.b.x) - state.crop.x)), y = Math.max(0, Math.min(canvas.height, Math.min(mark.a.y, mark.b.y) - state.crop.y));
        const right = Math.max(0, Math.min(canvas.width, Math.max(mark.a.x, mark.b.x) - state.crop.x)), bottom = Math.max(0, Math.min(canvas.height, Math.max(mark.a.y, mark.b.y) - state.crop.y));
        return {x: Math.round(x), y: Math.round(y), w: Math.round(right - x), h: Math.round(bottom - y)};
    }
    function draw(mark, preview = false) {
        context.save(); context.strokeStyle = context.fillStyle = mark.color; context.lineWidth = mark.width; context.lineCap = context.lineJoin = 'round';
        const a = {x: mark.a.x - state.crop.x, y: mark.a.y - state.crop.y}, b = mark.b && {x: mark.b.x - state.crop.x, y: mark.b.y - state.crop.y};
        if (mark.kind === 'pen') {
            context.beginPath(); mark.points.forEach((point, index) => { const x = point.x - state.crop.x, y = point.y - state.crop.y; index ? context.lineTo(x, y) : context.moveTo(x, y); }); context.stroke();
        } else if (mark.kind === 'text') {
            context.textBaseline = 'top'; context.font = `bold ${mark.size}px "Microsoft JhengHei", sans-serif`; context.fillText(mark.text, a.x, a.y);
        } else if (mark.kind === 'arrow') {
            const angle = Math.atan2(b.y - a.y, b.x - a.x), head = Math.max(12, mark.width * 4);
            context.beginPath(); context.moveTo(a.x, a.y); context.lineTo(b.x, b.y); context.stroke();
            context.beginPath(); context.moveTo(b.x, b.y); context.lineTo(b.x - head * Math.cos(angle - Math.PI / 6), b.y - head * Math.sin(angle - Math.PI / 6)); context.lineTo(b.x - head * Math.cos(angle + Math.PI / 6), b.y - head * Math.sin(angle + Math.PI / 6)); context.closePath(); context.fill();
        } else {
            const box = bounds(mark);
            if (mark.kind === 'rect') context.strokeRect(box.x, box.y, box.w, box.h);
            else if (preview || mark.kind === 'crop') { context.strokeStyle = '#60a5fa'; context.lineWidth = Math.max(2, canvas.width / 450); context.setLineDash([context.lineWidth * 4, context.lineWidth * 3]); context.strokeRect(box.x, box.y, box.w, box.h); }
            else if (mark.kind === 'cover') context.fillRect(box.x, box.y, box.w, box.h);
            else if (mark.kind === 'mosaic' && box.w && box.h) {
                const tiny = document.createElement('canvas'), pixel = Math.max(8, Math.round(Math.min(source.width, source.height) / 40));
                tiny.width = Math.max(1, Math.ceil(box.w / pixel)); tiny.height = Math.max(1, Math.ceil(box.h / pixel));
                tiny.getContext('2d').drawImage(canvas, box.x, box.y, box.w, box.h, 0, 0, tiny.width, tiny.height);
                context.imageSmoothingEnabled = false; context.clearRect(box.x, box.y, box.w, box.h); context.drawImage(tiny, box.x, box.y, box.w, box.h);
            }
        }
        context.restore();
    }
    function render() {
        if (!source) return;
        if (canvas.width !== state.crop.w) canvas.width = state.crop.w;
        if (canvas.height !== state.crop.h) canvas.height = state.crop.h;
        canvas.style.width = `${Math.min(canvas.width, 980)}px`;
        context.clearRect(0, 0, canvas.width, canvas.height);
        context.drawImage(source, state.crop.x, state.crop.y, state.crop.w, state.crop.h, 0, 0, canvas.width, canvas.height);
        state.marks.forEach(mark => draw(mark)); if (drag) draw(drag, true);
        controls();
    }
    async function add(files) {
        if (busy || !files.length) return;
        const file = files[0];
        if (file.size > 50 * 1024 * 1024 || !/^(image\/(png|jpeg|webp))$/.test(file.type)) { message('請加入 50 MB 以內的 PNG、JPG 或 WebP', true); return; }
        const ticket = ++generation; busy = true; controls();
        try {
            const bitmap = await createImageBitmap(file);
            if (ticket !== generation) { bitmap.close(); return; }
            if (bitmap.width * bitmap.height > 30000000) { bitmap.close(); throw new Error('圖片解析度超過 3000 萬像素'); }
            source?.close(); source = bitmap;
            state = {crop: {x: 0, y: 0, w: source.width, h: source.height}, marks: []}; undo.length = redo.length = 0; drag = null;
            $('editorName').value = `${file.name.replace(/\.[^.]+$/, '')}_標註`;
            canvas.classList.remove('hidden'); $('editorEmpty').hidden = true; render(); message(`已加入 ${source.width} × ${source.height} 圖片`);
        } catch (error) { message(`圖片無法讀取：${error.message}`, true); }
        finally { busy = false; controls(); }
    }
    ToolUI.upload($('editorDrop'), $('editorFile'), add, true);
    $('editorTools').querySelectorAll('button').forEach(button => button.addEventListener('click', () => { tool = button.dataset.tool; controls(); }));
    function point(event) {
        const box = canvas.getBoundingClientRect();
        return {x: state.crop.x + Math.max(0, Math.min(canvas.width, (event.clientX - box.left) * canvas.width / box.width)), y: state.crop.y + Math.max(0, Math.min(canvas.height, (event.clientY - box.top) * canvas.height / box.height))};
    }
    canvas.addEventListener('pointerdown', event => {
        if (!source || busy || event.button !== 0) return;
        if (state.marks.length >= 300 && tool !== 'crop') { message('目前最多 300 筆標註，請匯出圖片後再繼續', true); return; }
        if (!$('editorWidth').checkValidity() || !$('editorTextSize').checkValidity() || !$('editorWidth').value || !$('editorTextSize').value) { message('請檢查線條與文字大小', true); return; }
        event.preventDefault();
        const a = point(event), mark = {kind: tool, a, b: a, color: $('editorColor').value, width: Number($('editorWidth').value), size: Number($('editorTextSize').value)};
        if (tool === 'text') { if (!$('editorText').value.trim()) { message('請先輸入要加入的文字', true); return; } checkpoint(); mark.text = $('editorText').value; state.marks.push(mark); render(); return; }
        drag = {...mark, pointer: event.pointerId, points: [a]}; canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener('pointermove', event => { if (!drag || event.pointerId !== drag.pointer) return; drag.b = point(event); if (drag.kind === 'pen' && drag.points.length < 10000) drag.points.push(drag.b); if (frame === null) frame = requestAnimationFrame(() => { frame = null; render(); }); });
    canvas.addEventListener('pointerup', event => {
        if (!drag || event.pointerId !== drag.pointer) return;
        drag.b = point(event); const mark = drag; drag = null;
        if (Math.hypot(mark.b.x - mark.a.x, mark.b.y - mark.a.y) < 2 && mark.points.length < 2) { render(); return; }
        const box = bounds(mark);
        if (mark.kind === 'crop') {
            if (box.w < 2 || box.h < 2) { render(); message('請拖曳選取更大的裁切範圍', true); return; }
            checkpoint(); state.crop = {x: state.crop.x + box.x, y: state.crop.y + box.y, w: box.w, h: box.h}; message(`已裁切為 ${box.w} × ${box.h}，可按復原`);
        } else { checkpoint(); delete mark.pointer; state.marks.push(mark); }
        render();
    });
    canvas.addEventListener('pointercancel', () => { drag = null; render(); });
    function undoAction() { if (!undo.length || busy) return; drag = null; redo.push(structuredClone(state)); state = undo.pop(); render(); }
    function redoAction() { if (!redo.length || busy) return; drag = null; undo.push(structuredClone(state)); state = redo.pop(); render(); }
    $('editorUndo').addEventListener('click', undoAction); $('editorRedo').addEventListener('click', redoAction);
    document.addEventListener('keydown', event => { if (event.target.closest('input,textarea,select') || !source) return; if (event.ctrlKey && ['z', 'y'].includes(event.key.toLowerCase())) { event.preventDefault(); (event.key.toLowerCase() === 'y' || event.shiftKey ? redoAction : undoAction)(); } });
    function blob(format) {
        drag = null; render();
        let output = canvas;
        if (format === 'jpeg') { output = document.createElement('canvas'); output.width = canvas.width; output.height = canvas.height; const ctx = output.getContext('2d'); ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, output.width, output.height); ctx.drawImage(canvas, 0, 0); }
        return new Promise((resolve, reject) => output.toBlob(value => value ? resolve(value) : reject(new Error('瀏覽器無法匯出此格式')), `image/${format}`, .92));
    }
    $('editorDownload').addEventListener('click', async () => {
        if (busy || !source) return; busy = true; controls();
        try { const format = $('editorFormat').value; const value = await blob(format); if (value.type !== `image/${format}`) throw new Error('瀏覽器不支援此格式，請改用 PNG'); const name = ToolUI.filename($('editorName').value, '標註圖片').replace(/\.(png|jpe?g|webp)$/i, ''); ToolUI.download(value, `${name}.${format === 'jpeg' ? 'jpg' : format}`); message(`已匯出 ${canvas.width} × ${canvas.height} 圖片`); }
        catch (error) { message(error.message, true); } finally { busy = false; controls(); }
    });
    $('editorCopy').addEventListener('click', async () => {
        if (busy || !source) return; busy = true; controls();
        try { if (!navigator.clipboard?.write || !window.ClipboardItem) throw new Error('這個瀏覽器無法複製圖片，請使用下載'); const value = blob('png'); await navigator.clipboard.write([new ClipboardItem({'image/png': value})]); message('已複製圖片，可貼到聊天或文件'); }
        catch (error) { message(`複製失敗：${error.message}，可以改用下載`, true); } finally { busy = false; controls(); }
    });
    controls();
})();
