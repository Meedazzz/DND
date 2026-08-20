const { app, BrowserWindow, dialog, ipcMain, Menu, shell, session } = require('electron');
const { autoUpdater } = require('electron-updater');
const path = require('node:path');
const fs = require('node:fs/promises');
const http = require('node:http');
const os = require('node:os');
const { pathToFileURL } = require('node:url');

const PORT = Number(process.env.GRIMDICE_PORT || 4173);
const HOST = '0.0.0.0';
const APP_URL = `http://127.0.0.1:${PORT}`;
const RELEASES_URL = 'https://github.com/Meedazzz/DND/releases';
let mainWindow;
let serverHandle;
let updateTimer;
let updateState = {
  phase: 'idle',
  currentVersion: app.getVersion(),
  availableVersion: '',
  percent: 0,
  message: 'Проверка обновлений ещё не выполнялась.',
  checkedAt: ''
};

const hasLock = app.requestSingleInstanceLock();
if (!hasLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  });
}

function sendToRenderer(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send(channel, payload);
}

function setUpdateState(patch) {
  updateState = { ...updateState, ...patch };
  sendToRenderer('desktop:update-status', updateState);
  return updateState;
}

function setupUpdater() {
  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.allowPrerelease = false;
  autoUpdater.on('checking-for-update', () => setUpdateState({
    phase: 'checking',
    percent: 0,
    message: 'Проверяем GitHub Releases…'
  }));
  autoUpdater.on('update-available', (info) => setUpdateState({
    phase: 'available',
    availableVersion: info?.version || '',
    checkedAt: new Date().toISOString(),
    message: `Доступна версия ${info?.version || 'новее текущей'}.`
  }));
  autoUpdater.on('update-not-available', () => setUpdateState({
    phase: 'current',
    availableVersion: '',
    checkedAt: new Date().toISOString(),
    message: 'Установлена актуальная версия.'
  }));
  autoUpdater.on('download-progress', (progress) => setUpdateState({
    phase: 'downloading',
    percent: Math.max(0, Math.min(100, Math.round(progress?.percent || 0))),
    message: `Загрузка обновления: ${Math.round(progress?.percent || 0)}%`
  }));
  autoUpdater.on('update-downloaded', (info) => setUpdateState({
    phase: 'ready',
    percent: 100,
    availableVersion: info?.version || updateState.availableVersion,
    message: 'Обновление загружено. Его можно установить сейчас или при выходе.'
  }));
  autoUpdater.on('error', (error) => setUpdateState({
    phase: 'error',
    message: `Не удалось обновить: ${String(error?.message || error)}`
  }));

  if (app.isPackaged) {
    setTimeout(() => checkForUpdates(false), 12_000);
    updateTimer = setInterval(() => checkForUpdates(false), 6 * 60 * 60 * 1000);
  } else {
    setUpdateState({ phase: 'development', message: 'Обновления проверяются только в установленной сборке.' });
  }
}

async function checkForUpdates(interactive = true) {
  if (!app.isPackaged) {
    return setUpdateState({ phase: 'development', message: 'В режиме разработки обновления отключены.' });
  }
  if (['checking', 'downloading'].includes(updateState.phase)) return updateState;
  try {
    await autoUpdater.checkForUpdates();
  } catch (error) {
    setUpdateState({ phase: 'error', message: `Не удалось проверить обновления: ${String(error?.message || error)}` });
    if (interactive && mainWindow) {
      dialog.showMessageBox(mainWindow, {
        type: 'warning',
        title: 'Обновление GrimDice',
        message: 'Не удалось проверить обновления.',
        detail: String(error?.message || error)
      });
    }
  }
  return updateState;
}

async function downloadUpdate() {
  if (!app.isPackaged) return setUpdateState({ phase: 'development', message: 'Загрузка доступна только в установленной сборке.' });
  if (updateState.phase !== 'available') return updateState;
  try {
    setUpdateState({ phase: 'downloading', percent: 0, message: 'Начинаем загрузку обновления…' });
    await autoUpdater.downloadUpdate();
  } catch (error) {
    setUpdateState({ phase: 'error', message: `Не удалось загрузить обновление: ${String(error?.message || error)}` });
  }
  return updateState;
}

function installUpdate() {
  if (updateState.phase !== 'ready') return false;
  setImmediate(() => autoUpdater.quitAndInstall(false, true));
  return true;
}

async function waitForServer(url, attempts = 80) {
  for (let index = 0; index < attempts; index += 1) {
    const ready = await new Promise((resolve) => {
      const req = http.get(`${url}/api/health`, (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      });
      req.setTimeout(350, () => {
        req.destroy();
        resolve(false);
      });
      req.on('error', () => resolve(false));
    });
    if (ready) return;
    await new Promise((resolve) => setTimeout(resolve, 125));
  }
  throw new Error('Локальный сервер GrimDice не запустился вовремя.');
}

async function startEmbeddedServer() {
  process.env.PORT = String(PORT);
  process.env.HOST = HOST;
  process.env.GRIMDICE_DATA_DIR = app.getPath('userData');
  const serverPath = app.isPackaged
    ? path.join(process.resourcesPath, 'app.asar.unpacked', 'server.mjs')
    : path.join(__dirname, '..', 'server.mjs');
  const serverModule = await import(`${pathToFileURL(serverPath).href}?desktop=${Date.now()}`);
  if (typeof serverModule.startServer !== 'function') throw new Error('server.mjs does not export startServer().');
  serverHandle = await serverModule.startServer({ port: PORT, host: HOST });
  await waitForServer(APP_URL);
}

async function saveCampaign(defaultName, content) {
  const result = await dialog.showSaveDialog(mainWindow, {
    title: 'Сохранить кампанию GrimDice',
    defaultPath: defaultName || 'campaign.grimdice.json',
    filters: [
      { name: 'Кампания GrimDice', extensions: ['json'] },
      { name: 'Все файлы', extensions: ['*'] }
    ]
  });
  if (result.canceled || !result.filePath) return { canceled: true };
  await fs.writeFile(result.filePath, content, 'utf8');
  return { canceled: false, path: result.filePath };
}

async function openCampaign() {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Открыть кампанию GrimDice',
    properties: ['openFile'],
    filters: [
      { name: 'Кампания GrimDice', extensions: ['json'] },
      { name: 'Все файлы', extensions: ['*'] }
    ]
  });
  if (result.canceled || !result.filePaths[0]) return { canceled: true };
  const content = await fs.readFile(result.filePaths[0], 'utf8');
  return { canceled: false, path: result.filePaths[0], content };
}

function buildMenu() {
  const template = [
    {
      label: 'Кампания',
      submenu: [
        { label: 'Открыть…', accelerator: 'CmdOrCtrl+O', click: () => sendToRenderer('desktop:menu', 'open') },
        { label: 'Сохранить как…', accelerator: 'CmdOrCtrl+Shift+S', click: () => sendToRenderer('desktop:menu', 'save-as') },
        { type: 'separator' },
        { role: process.platform === 'darwin' ? 'close' : 'quit', label: process.platform === 'darwin' ? 'Закрыть окно' : 'Выход' }
      ]
    },
    {
      label: 'Правка',
      submenu: [
        { role: 'undo', label: 'Отменить' },
        { role: 'redo', label: 'Повторить' },
        { type: 'separator' },
        { role: 'cut', label: 'Вырезать' },
        { role: 'copy', label: 'Копировать' },
        { role: 'paste', label: 'Вставить' },
        { role: 'selectAll', label: 'Выделить всё' }
      ]
    },
    {
      label: 'Вид',
      submenu: [
        { role: 'reload', label: 'Перезагрузить' },
        { role: 'togglefullscreen', label: 'Полный экран' },
        { role: 'resetZoom', label: 'Масштаб 100%' },
        { role: 'zoomIn', label: 'Увеличить' },
        { role: 'zoomOut', label: 'Уменьшить' }
      ]
    },
    {
      label: 'Обновление',
      submenu: [
        { label: 'Проверить обновления…', click: () => checkForUpdates(true) },
        { label: 'Страница релизов', click: () => shell.openExternal(RELEASES_URL) }
      ]
    }
  ];
  if (process.platform === 'darwin') template.unshift({ label: app.name, submenu: [{ role: 'about' }, { type: 'separator' }, { role: 'quit' }] });
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    title: 'GrimDice',
    width: 1560,
    height: 980,
    minWidth: 1120,
    minHeight: 720,
    backgroundColor: '#0b0b0e',
    autoHideMenuBar: false,
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  mainWindow.webContents.on('will-navigate', (event, url) => {
    try { if (new URL(url).origin !== APP_URL) event.preventDefault(); }
    catch { event.preventDefault(); }
  });
  mainWindow.loadURL(APP_URL);
  mainWindow.on('closed', () => { mainWindow = undefined; });
}

ipcMain.handle('desktop:save-campaign', (_event, payload = {}) => saveCampaign(payload.defaultName, payload.content));
ipcMain.handle('desktop:open-campaign', () => openCampaign());
ipcMain.handle('desktop:network-info', () => ({
  port: PORT,
  addresses: Object.entries(os.networkInterfaces()).flatMap(([name, rows]) => (rows || [])
    .filter((row) => row.family === 'IPv4' && !row.internal)
    .map((row) => ({ name, address: row.address })))
}));
ipcMain.handle('desktop:update-state', () => updateState);
ipcMain.handle('desktop:check-update', () => checkForUpdates(true));
ipcMain.handle('desktop:download-update', () => downloadUpdate());
ipcMain.handle('desktop:install-update', () => installUpdate());
ipcMain.handle('desktop:open-releases', () => shell.openExternal(RELEASES_URL));

if (hasLock) {
  app.whenReady().then(async () => {
    try {
      session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
      await startEmbeddedServer();
      buildMenu();
      createWindow();
      setupUpdater();
    } catch (error) {
      dialog.showErrorBox('GrimDice', String(error?.stack || error));
      app.quit();
    }
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });
}

app.on('before-quit', () => {
  if (updateTimer) clearInterval(updateTimer);
  if (serverHandle?.server) serverHandle.server.close?.();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
