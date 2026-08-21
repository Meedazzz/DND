(() => {
  'use strict';

  const DEFAULTS = Object.freeze({
    crop: 'original', width: 1280, rotation: 0, flipX: false, flipY: false,
    brightness: 0, contrast: 0, saturation: 0, hue: 0, blur: 0,
    sepia: 0, grayscale: 0, vignette: 0, grain: 0,
    tint: '#6d1f1b', tintAmount: 0, border: 0, borderColor: '#c59b57',
    chroma: false, chromaColor: '#00ff00', chromaTolerance: 55,
    caption: '', captionColor: '#f0dfb6', captionSize: 42,
    format: 'image/png', quality: 0.92, zoom: 100
  });

  const PRESETS = Object.freeze({
    clean: { brightness: 0, contrast: 0, saturation: 0, hue: 0, blur: 0, sepia: 0, grayscale: 0, vignette: 0, grain: 0, tintAmount: 0 },
    gothic: { brightness: -12, contrast: 30, saturation: -30, hue: 0, sepia: 24, grayscale: 0, vignette: 56, grain: 16, tint: '#4d171a', tintAmount: 8 },
    ember: { brightness: 4, contrast: 20, saturation: 10, hue: -8, sepia: 30, grayscale: 0, vignette: 40, grain: 10, tint: '#7a1c14', tintAmount: 13 },
    moon: { brightness: -4, contrast: 22, saturation: -48, hue: 174, sepia: 4, grayscale: 0, vignette: 45, grain: 8, tint: '#17324d', tintAmount: 15 },
    ink: { brightness: -8, contrast: 48, saturation: -100, hue: 0, sepia: 12, grayscale: 28, vignette: 62, grain: 20, tintAmount: 0 }
  });

  const state = {
    source: null,
    sourceName: '',
    sourceWidth: 0,
    sourceHeight: 0,
    settings: { ...DEFAULTS },
    history: [],
    historyIndex: -1,
    compare: false,
    busy: false,
    root: null,
    canvas: null
  };

  const cloneSettings = () => JSON.parse(JSON.stringify(state.settings));
  const clamp = (value, min, max) => Math.min(max, Math.max(min, Number(value) || 0));
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));

  function renderMarkup() {
    const hasSource = Boolean(state.source);
    return `
      <section class="panel photo-editor-shell" aria-label="Редактор изображений">
        <div class="section-head editor-head">
          <div>
            <div class="eyebrow">ВИЗУАЛЬНАЯ МАСТЕРСКАЯ</div>
            <h2>Редактор изображений</h2>
            <p>Локальная обработка без загрузки файлов в облако: кадрирование, размер, цвет, эффекты, хромакей, подпись и экспорт.</p>
          </div>
          <div class="editor-head-actions">
            <label class="button primary editor-file-button">Импортировать
              <input id="photoEditorInput" type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden>
            </label>
            <button class="button" data-editor-action="undo" ${state.historyIndex <= 0 ? 'disabled' : ''}>↶ Отменить</button>
            <button class="button" data-editor-action="redo" ${state.historyIndex >= state.history.length - 1 ? 'disabled' : ''}>↷ Вернуть</button>
            <button class="button" data-editor-action="reset" ${hasSource ? '' : 'disabled'}>Сбросить</button>
          </div>
        </div>

        <div class="photo-editor-layout">
          <aside class="editor-tools" aria-label="Инструменты обработки">
            <details open>
              <summary>Геометрия</summary>
              <div class="editor-control-grid">
                <label>Кадр
                  <select data-editor-key="crop">
                    <option value="original">Исходный</option><option value="1:1">1:1</option>
                    <option value="16:9">16:9</option><option value="4:3">4:3</option>
                    <option value="4:5">4:5</option><option value="9:16">9:16</option>
                  </select>
                </label>
                <label>Ширина, px<input data-editor-key="width" type="number" min="64" max="4096" step="1"></label>
              </div>
              <div class="editor-button-row">
                <button class="button small" data-editor-action="rotate-left">↶ 90°</button>
                <button class="button small" data-editor-action="rotate-right">↷ 90°</button>
                <button class="button small" data-editor-action="flip-x">↔ Отразить</button>
                <button class="button small" data-editor-action="flip-y">↕ Отразить</button>
              </div>
            </details>

            <details open>
              <summary>Свет и цвет</summary>
              ${rangeControl('brightness', 'Яркость', -100, 100)}
              ${rangeControl('contrast', 'Контраст', -100, 100)}
              ${rangeControl('saturation', 'Насыщенность', -100, 100)}
              ${rangeControl('hue', 'Тон', -180, 180, '°')}
              ${rangeControl('sepia', 'Сепия', 0, 100)}
              ${rangeControl('grayscale', 'Монохром', 0, 100)}
            </details>

            <details>
              <summary>Эффекты и края</summary>
              ${rangeControl('blur', 'Размытие', 0, 20, ' px')}
              ${rangeControl('vignette', 'Виньетка', 0, 100)}
              ${rangeControl('grain', 'Зерно', 0, 100)}
              <div class="editor-control-grid">
                <label>Тонирование<input data-editor-key="tint" type="color"></label>
                <label>Сила<input data-editor-key="tintAmount" type="number" min="0" max="100"></label>
                <label>Рамка<input data-editor-key="border" type="number" min="0" max="100"></label>
                <label>Цвет рамки<input data-editor-key="borderColor" type="color"></label>
              </div>
            </details>

            <details>
              <summary>Хромакей</summary>
              <label class="editor-check"><input data-editor-key="chroma" type="checkbox"> Удалять выбранный фон</label>
              <div class="editor-control-grid">
                <label>Цвет<input data-editor-key="chromaColor" type="color"></label>
                <label>Допуск<input data-editor-key="chromaTolerance" type="number" min="0" max="255"></label>
              </div>
              <p class="micro">Для прозрачности экспортируйте PNG или WebP.</p>
            </details>

            <details>
              <summary>Подпись</summary>
              <label>Текст<input data-editor-key="caption" maxlength="160" placeholder="Название сцены или персонажа"></label>
              <div class="editor-control-grid">
                <label>Цвет<input data-editor-key="captionColor" type="color"></label>
                <label>Размер<input data-editor-key="captionSize" type="number" min="12" max="180"></label>
              </div>
            </details>
          </aside>

          <div class="editor-stage-column">
            <div class="editor-presets" aria-label="Предустановки">
              <span>Образы:</span>
              <button class="chip" data-editor-preset="clean">Чистый</button>
              <button class="chip" data-editor-preset="gothic">Готика</button>
              <button class="chip" data-editor-preset="ember">Угли</button>
              <button class="chip" data-editor-preset="moon">Лунный</button>
              <button class="chip" data-editor-preset="ink">Гравюра</button>
            </div>
            <div class="editor-dropzone ${hasSource ? 'has-source' : ''}" id="photoEditorDropzone">
              <canvas id="photoEditorCanvas" aria-label="Предпросмотр изображения"></canvas>
              <div class="editor-empty" ${hasSource ? 'hidden' : ''}>
                <div class="editor-empty-icon">✦</div>
                <strong>Перетащите изображение сюда</strong>
                <span>PNG, JPEG, WebP или GIF. Обработка остаётся на этом устройстве.</span>
              </div>
            </div>
            <div class="editor-preview-bar">
              <button class="button small" data-editor-action="compare" ${hasSource ? '' : 'disabled'}>${state.compare ? 'Показать результат' : 'Удерживать «до»'}</button>
              <label class="editor-zoom">Масштаб <input data-editor-key="zoom" type="range" min="25" max="150"><output data-editor-output="zoom"></output></label>
              <span id="photoEditorDimensions">${hasSource ? `${state.sourceWidth} × ${state.sourceHeight} px` : 'Изображение не выбрано'}</span>
            </div>
          </div>

          <aside class="editor-export" aria-label="Экспорт изображения">
            <div class="editor-export-card">
              <div class="eyebrow">РЕЗУЛЬТАТ</div>
              <h3>Сохранение</h3>
              <label>Формат
                <select data-editor-key="format">
                  <option value="image/png">PNG — прозрачность</option>
                  <option value="image/jpeg">JPEG — фотография</option>
                  <option value="image/webp">WebP — компактно</option>
                </select>
              </label>
              ${rangeControl('quality', 'Качество JPEG / WebP', 0.1, 1, '', 0.01)}
              <button class="button wide" data-editor-action="export" ${hasSource ? '' : 'disabled'}>Скачать файл</button>
            </div>
            <div class="editor-export-card">
              <div class="eyebrow">БИБЛИОТЕКА GM</div>
              <h3>Добавить в кампанию</h3>
              <label>Категория
                <select id="photoEditorCategory">
                  <option value="backgrounds">Фоны сцен</option>
                  <option value="maps">Карты</option>
                  <option value="portraits">Портреты</option>
                  <option value="sprites">Спрайты</option>
                  <option value="effects">Эффекты</option>
                </select>
              </label>
              <label>Название<input id="photoEditorTitle" maxlength="80" placeholder="Название ресурса"></label>
              <button class="button primary wide" data-editor-action="save-library" ${hasSource ? '' : 'disabled'}>Сохранить в библиотеку</button>
              <p class="micro">Обработанное изображение сохранится в медиатеке текущей кампании и может быть назначено сцене или персонажу.</p>
            </div>
            <div id="photoEditorStatus" class="editor-status" role="status">Готово к работе.</div>
          </aside>
        </div>
      </section>`;
  }

  function rangeControl(key, label, min, max, suffix = '%', step = 1) {
    return `<label class="editor-range"><span>${label}<output data-editor-output="${key}"></output></span><input data-editor-key="${key}" type="range" min="${min}" max="${max}" step="${step}"></label>`;
  }

  function ratioValue(value) {
    if (value === 'original') return state.sourceWidth && state.sourceHeight ? state.sourceWidth / state.sourceHeight : 1;
    const [width, height] = value.split(':').map(Number);
    return width / height;
  }

  function sourceCrop() {
    const sourceRatio = state.sourceWidth / state.sourceHeight;
    const targetRatio = ratioValue(state.settings.crop);
    if (!Number.isFinite(targetRatio) || Math.abs(sourceRatio - targetRatio) < 0.0001) {
      return { x: 0, y: 0, width: state.sourceWidth, height: state.sourceHeight };
    }
    if (sourceRatio > targetRatio) {
      const width = state.sourceHeight * targetRatio;
      return { x: (state.sourceWidth - width) / 2, y: 0, width, height: state.sourceHeight };
    }
    const height = state.sourceWidth / targetRatio;
    return { x: 0, y: (state.sourceHeight - height) / 2, width: state.sourceWidth, height };
  }

  function dimensions() {
    const crop = sourceCrop();
    const width = clamp(Math.round(state.settings.width), 64, 4096);
    const height = clamp(Math.round(width * crop.height / crop.width), 64, 4096);
    const quarterTurn = Math.abs(state.settings.rotation % 180) === 90;
    return {
      drawWidth: width,
      drawHeight: height,
      width: quarterTurn ? height : width,
      height: quarterTurn ? width : height,
      crop
    };
  }

  function hexToRgb(hex) {
    const clean = String(hex || '#000000').replace('#', '');
    const value = Number.parseInt(clean.length === 3 ? clean.split('').map((part) => part + part).join('') : clean, 16);
    return { r: (value >> 16) & 255, g: (value >> 8) & 255, b: value & 255 };
  }

  function renderCanvas() {
    const canvas = state.canvas;
    if (!canvas || typeof canvas.getContext !== 'function') return;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    if (!context) return;
    if (!state.source) {
      canvas.width = 960;
      canvas.height = 540;
      context.fillStyle = '#0a0a0d';
      context.fillRect(0, 0, canvas.width, canvas.height);
      return;
    }

    const size = dimensions();
    canvas.width = size.width;
    canvas.height = size.height;
    canvas.style.width = `${state.settings.zoom}%`;
    canvas.style.maxWidth = 'none';
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.save();
    context.translate(canvas.width / 2, canvas.height / 2);
    context.rotate((state.settings.rotation * Math.PI) / 180);
    context.scale(state.settings.flipX ? -1 : 1, state.settings.flipY ? -1 : 1);

    const current = state.compare ? DEFAULTS : state.settings;
    context.filter = [
      `brightness(${100 + Number(current.brightness)}%)`,
      `contrast(${100 + Number(current.contrast)}%)`,
      `saturate(${100 + Number(current.saturation)}%)`,
      `hue-rotate(${Number(current.hue)}deg)`,
      `sepia(${Number(current.sepia)}%)`,
      `grayscale(${Number(current.grayscale)}%)`,
      `blur(${Number(current.blur)}px)`
    ].join(' ');
    context.drawImage(
      state.source,
      size.crop.x, size.crop.y, size.crop.width, size.crop.height,
      -size.drawWidth / 2, -size.drawHeight / 2, size.drawWidth, size.drawHeight
    );
    context.restore();
    context.filter = 'none';

    if (!state.compare && state.settings.chroma) applyChroma(context, canvas);
    if (!state.compare && Number(state.settings.tintAmount) > 0) {
      context.save();
      context.globalCompositeOperation = 'source-atop';
      context.globalAlpha = clamp(state.settings.tintAmount, 0, 100) / 100;
      context.fillStyle = state.settings.tint;
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.restore();
    }
    if (!state.compare && Number(state.settings.vignette) > 0) drawVignette(context, canvas);
    if (!state.compare && Number(state.settings.grain) > 0) drawGrain(context, canvas);
    if (!state.compare && Number(state.settings.border) > 0) drawBorder(context, canvas);
    if (!state.compare && state.settings.caption.trim()) drawCaption(context, canvas);

    const sizeLabel = state.root?.querySelector?.('#photoEditorDimensions');
    if (sizeLabel) sizeLabel.textContent = `${canvas.width} × ${canvas.height} px · исходник ${state.sourceWidth} × ${state.sourceHeight}`;
  }

  function applyChroma(context, canvas) {
    try {
      const image = context.getImageData(0, 0, canvas.width, canvas.height);
      const target = hexToRgb(state.settings.chromaColor);
      const threshold = clamp(state.settings.chromaTolerance, 0, 255) * 1.73;
      for (let index = 0; index < image.data.length; index += 4) {
        const distance = Math.hypot(image.data[index] - target.r, image.data[index + 1] - target.g, image.data[index + 2] - target.b);
        if (distance <= threshold) image.data[index + 3] = Math.round(image.data[index + 3] * (distance / Math.max(1, threshold)));
      }
      context.putImageData(image, 0, 0);
    } catch (_error) {
      setStatus('Хромакей недоступен для этого источника.', 'warn');
    }
  }

  function drawVignette(context, canvas) {
    const radius = Math.max(canvas.width, canvas.height) * 0.72;
    const gradient = context.createRadialGradient(canvas.width / 2, canvas.height / 2, radius * 0.18, canvas.width / 2, canvas.height / 2, radius);
    gradient.addColorStop(0, 'rgba(0,0,0,0)');
    gradient.addColorStop(1, `rgba(0,0,0,${clamp(state.settings.vignette, 0, 100) / 100})`);
    context.fillStyle = gradient;
    context.fillRect(0, 0, canvas.width, canvas.height);
  }

  function drawGrain(context, canvas) {
    const amount = clamp(state.settings.grain, 0, 100);
    const samples = Math.min(12000, Math.floor(canvas.width * canvas.height * amount / 2600));
    let seed = (canvas.width * 73856093) ^ (canvas.height * 19349663) ^ amount;
    context.save();
    for (let index = 0; index < samples; index += 1) {
      seed = (seed * 1664525 + 1013904223) >>> 0;
      const x = seed % canvas.width;
      seed = (seed * 1664525 + 1013904223) >>> 0;
      const y = seed % canvas.height;
      context.fillStyle = seed & 1 ? `rgba(255,240,215,${amount / 950})` : `rgba(0,0,0,${amount / 720})`;
      const point = Math.max(1, Math.round(Math.min(canvas.width, canvas.height) / 900));
      context.fillRect(x, y, point, point);
    }
    context.restore();
  }

  function drawBorder(context, canvas) {
    const thickness = Math.min(Math.min(canvas.width, canvas.height) / 3, Number(state.settings.border));
    context.save();
    context.strokeStyle = state.settings.borderColor;
    context.lineWidth = thickness;
    context.strokeRect(thickness / 2, thickness / 2, canvas.width - thickness, canvas.height - thickness);
    context.restore();
  }

  function drawCaption(context, canvas) {
    const fontSize = clamp(state.settings.captionSize, 12, Math.max(12, canvas.height / 4));
    const padding = Math.max(16, fontSize * 0.7);
    context.save();
    context.font = `700 ${fontSize}px Georgia, serif`;
    context.textAlign = 'center';
    context.textBaseline = 'bottom';
    const text = state.settings.caption.trim().slice(0, 160);
    const measured = Math.min(canvas.width - padding * 2, context.measureText(text).width + padding * 1.3);
    context.fillStyle = 'rgba(4,4,6,.68)';
    context.fillRect((canvas.width - measured) / 2, canvas.height - fontSize - padding * 1.45, measured, fontSize + padding);
    context.shadowColor = 'rgba(0,0,0,.9)';
    context.shadowBlur = Math.max(2, fontSize / 9);
    context.fillStyle = state.settings.captionColor;
    context.fillText(text, canvas.width / 2, canvas.height - padding * 0.72, canvas.width - padding * 2);
    context.restore();
  }

  function pushHistory() {
    const snapshot = cloneSettings();
    const current = state.history[state.historyIndex];
    if (current && JSON.stringify(current) === JSON.stringify(snapshot)) return;
    state.history = state.history.slice(0, state.historyIndex + 1);
    state.history.push(snapshot);
    if (state.history.length > 40) state.history.shift();
    state.historyIndex = state.history.length - 1;
    syncUndoButtons();
  }

  function restoreHistory(offset) {
    const nextIndex = clamp(state.historyIndex + offset, 0, state.history.length - 1);
    if (nextIndex === state.historyIndex) return;
    state.historyIndex = nextIndex;
    state.settings = JSON.parse(JSON.stringify(state.history[nextIndex]));
    syncControls();
    renderCanvas();
    syncUndoButtons();
  }

  function syncUndoButtons() {
    const undo = state.root?.querySelector?.('[data-editor-action="undo"]');
    const redo = state.root?.querySelector?.('[data-editor-action="redo"]');
    if (undo) undo.disabled = state.historyIndex <= 0;
    if (redo) redo.disabled = state.historyIndex >= state.history.length - 1;
  }

  function syncControls() {
    for (const element of state.root?.querySelectorAll?.('[data-editor-key]') || []) {
      const key = element.dataset.editorKey;
      if (!(key in state.settings)) continue;
      if (element.type === 'checkbox') element.checked = Boolean(state.settings[key]);
      else element.value = state.settings[key];
    }
    for (const output of state.root?.querySelectorAll?.('[data-editor-output]') || []) {
      const key = output.dataset.editorOutput;
      const value = state.settings[key];
      output.value = key === 'hue' ? `${value}°` : key === 'blur' ? `${value} px` : key === 'quality' ? `${Math.round(value * 100)}%` : `${value}%`;
      output.textContent = output.value;
    }
  }

  function setStatus(message, tone = '') {
    const node = state.root?.querySelector?.('#photoEditorStatus');
    if (!node) return;
    node.textContent = message;
    node.dataset.tone = tone;
  }

  async function decodeFile(file) {
    if (!file || !String(file.type).startsWith('image/')) throw new Error('Выберите файл изображения.');
    if (file.size > 80 * 1024 * 1024) throw new Error('Файл больше 80 МБ. Уменьшите его перед импортом.');
    if (typeof createImageBitmap === 'function') return createImageBitmap(file);
    return new Promise((resolve, reject) => {
      const image = new Image();
      const url = URL.createObjectURL(file);
      image.onload = () => { URL.revokeObjectURL(url); resolve(image); };
      image.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Не удалось декодировать изображение.')); };
      image.src = url;
    });
  }

  async function importFile(file) {
    if (state.busy) return;
    state.busy = true;
    setStatus('Открываем изображение…');
    try {
      const source = await decodeFile(file);
      if (typeof state.source?.close === 'function') state.source.close();
      state.source = source;
      state.sourceName = file.name || 'image.png';
      state.sourceWidth = source.naturalWidth || source.width;
      state.sourceHeight = source.naturalHeight || source.height;
      state.settings = { ...DEFAULTS, width: Math.min(1920, state.sourceWidth) };
      state.history = [cloneSettings()];
      state.historyIndex = 0;
      state.compare = false;
      const title = state.root?.querySelector?.('#photoEditorTitle');
      if (title) title.value = state.sourceName.replace(/\.[^.]+$/, '');
      state.root?.querySelector?.('.editor-empty')?.setAttribute?.('hidden', '');
      state.root?.querySelector?.('#photoEditorDropzone')?.classList?.add?.('has-source');
      for (const button of state.root?.querySelectorAll?.('[data-editor-action="reset"], [data-editor-action="compare"], [data-editor-action="export"], [data-editor-action="save-library"]') || []) button.disabled = false;
      syncControls();
      renderCanvas();
      syncUndoButtons();
      setStatus(`Открыто: ${state.sourceName} · ${state.sourceWidth} × ${state.sourceHeight} px`, 'ok');
    } catch (error) {
      setStatus(String(error?.message || error), 'error');
    } finally {
      state.busy = false;
    }
  }

  function applyPreset(name) {
    if (!PRESETS[name]) return;
    Object.assign(state.settings, PRESETS[name]);
    state.compare = false;
    pushHistory();
    syncControls();
    renderCanvas();
    setStatus(`Применён образ «${name}».`, 'ok');
  }

  function extensionFor(mime) {
    if (mime === 'image/jpeg') return 'jpg';
    if (mime === 'image/webp') return 'webp';
    return 'png';
  }

  function outputName() {
    const base = (state.sourceName || 'image').replace(/\.[^.]+$/, '').replace(/[^\p{L}\p{N}._-]+/gu, '-').replace(/^-+|-+$/g, '') || 'image';
    return `${base}-edited.${extensionFor(state.settings.format)}`;
  }

  function canvasBlob() {
    return new Promise((resolve, reject) => {
      if (!state.canvas || !state.source) return reject(new Error('Сначала импортируйте изображение.'));
      state.canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('Браузер не смог создать файл.')), state.settings.format, Number(state.settings.quality));
    });
  }

  async function exportFile() {
    try {
      const blob = await canvasBlob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = outputName();
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      setStatus(`Экспортировано: ${anchor.download}`, 'ok');
    } catch (error) {
      setStatus(String(error?.message || error), 'error');
    }
  }

  async function saveToLibrary() {
    if (state.busy) return;
    state.busy = true;
    setStatus('Сохраняем в библиотеку…');
    try {
      const blob = await canvasBlob();
      const category = state.root?.querySelector?.('#photoEditorCategory')?.value || 'backgrounds';
      const title = state.root?.querySelector?.('#photoEditorTitle')?.value.trim() || outputName().replace(/\.[^.]+$/, '');
      const event = new CustomEvent('dragon-saga-image-save', {
        detail: {
          blob,
          name: outputName(),
          title,
          kind: category,
          mime: blob.type,
          width: state.canvas.width,
          height: state.canvas.height
        }
      });
      document.dispatchEvent(event);
      setStatus(`Передано в библиотеку: ${title}`, 'ok');
    } catch (error) {
      setStatus(String(error?.message || error), 'error');
    } finally {
      state.busy = false;
    }
  }

  function handleAction(action) {
    if (action === 'undo') return restoreHistory(-1);
    if (action === 'redo') return restoreHistory(1);
    if (action === 'export') return exportFile();
    if (action === 'save-library') return saveToLibrary();
    if (action === 'compare') {
      state.compare = !state.compare;
      const button = state.root?.querySelector?.('[data-editor-action="compare"]');
      if (button) button.textContent = state.compare ? 'Показать результат' : 'Удерживать «до»';
      renderCanvas();
      return;
    }
    if (!state.source) return;
    if (action === 'rotate-left') state.settings.rotation = (state.settings.rotation + 270) % 360;
    if (action === 'rotate-right') state.settings.rotation = (state.settings.rotation + 90) % 360;
    if (action === 'flip-x') state.settings.flipX = !state.settings.flipX;
    if (action === 'flip-y') state.settings.flipY = !state.settings.flipY;
    if (action === 'reset') {
      const width = Math.min(1920, state.sourceWidth);
      state.settings = { ...DEFAULTS, width };
    }
    state.compare = false;
    pushHistory();
    syncControls();
    renderCanvas();
  }

  function mount(root) {
    state.root = root;
    state.canvas = root?.querySelector?.('#photoEditorCanvas') || null;
    if (!root || root.dataset?.editorMounted === 'true') {
      syncControls();
      renderCanvas();
      return;
    }
    if (root.dataset) root.dataset.editorMounted = 'true';

    root.addEventListener('click', (event) => {
      const action = event.target.closest?.('[data-editor-action]')?.dataset.editorAction;
      const preset = event.target.closest?.('[data-editor-preset]')?.dataset.editorPreset;
      if (action) handleAction(action);
      if (preset) applyPreset(preset);
    });
    root.addEventListener('input', (event) => {
      const key = event.target.dataset?.editorKey;
      if (!key || !(key in state.settings)) return;
      if (event.target.type === 'checkbox') state.settings[key] = event.target.checked;
      else if (['crop', 'format', 'tint', 'borderColor', 'chromaColor', 'caption'].includes(key)) state.settings[key] = event.target.value;
      else state.settings[key] = Number(event.target.value);
      syncControls();
      renderCanvas();
    });
    root.addEventListener('change', (event) => {
      if (event.target.id === 'photoEditorInput') return importFile(event.target.files?.[0]);
      if (event.target.dataset?.editorKey) pushHistory();
    });
    root.addEventListener('keydown', (event) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'z') return;
      event.preventDefault();
      restoreHistory(event.shiftKey ? 1 : -1);
    });
    const dropzone = root.querySelector?.('#photoEditorDropzone');
    dropzone?.addEventListener?.('dragover', (event) => { event.preventDefault(); dropzone.classList.add('is-dragging'); });
    dropzone?.addEventListener?.('dragleave', () => dropzone.classList.remove('is-dragging'));
    dropzone?.addEventListener?.('drop', (event) => {
      event.preventDefault();
      dropzone.classList.remove('is-dragging');
      importFile(event.dataTransfer?.files?.[0]);
    });

    syncControls();
    renderCanvas();
    syncUndoButtons();
  }

  window.DragonSagaImageEditor = Object.freeze({
    renderMarkup,
    mount,
    capabilities: Object.freeze(['import', 'crop', 'resize', 'rotate', 'flip', 'color', 'filters', 'vignette', 'grain', 'chroma-key', 'caption', 'undo-redo', 'export', 'campaign-library'])
  });
})();
