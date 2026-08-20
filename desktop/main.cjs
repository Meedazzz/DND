const { app, BrowserWindow, ipcMain, dialog, Menu, shell } = require('electron');
const path = require('node:path');
const os = require('node:os');
const { pathToFileURL } = require('node:url');

let mainWindow = null;
let localServer = null;
let localPort = null;

function localAddresses() {
  const result = [];
  for (const entries of Object.values(os.networkInterfaces())) {
    for (const entry of entries || []) {
      if (entry.family === 'IPv4' && !entry.internal) result.push({ name: entry.address.startsWith('25.') ? 'Hamachi' : 'LAN', address: entry.address });
    }
  }
  return result;
}

async function startLocalServer() {
  const appRoot = app.isPackaged ? path.join(process.resourcesPath, 'app.asar.unpacked') : path.join(__dirname, '..');
  const moduleUrl = pathToFileURL(path.join(appRoot, 'server.mjs')).href;
  const { startServer } = await import(moduleUrl);
  const started = await startServer({ port: 0, host: '0.0.0.0' });
  localServer = started.server;
  return started.port;
}

async function createWindow() {
  const port = await startLocalServer();
  localPort = port;
  mainWindow = new BrowserWindow({
    width: 1500,
    height: 940,
    minWidth: 1080,
    minHeight: 700,
    backgroundColor: '#0d0c0d',
    title: 'GrimDice — мастерская боя 5e',
    show: false,
    autoHideMenuBar: true,
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/i.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  await mainWindow.loadURL(`http://127.0.0.1:${port}/?desktop=1`);
}

function installMenu() {
  const template = [
    {
      label: 'Файл', submenu: [
        { label: 'Новая кампания', accelerator: 'CmdOrCtrl+N', click: () => mainWindow?.webContents.send('desktop-command', 'new') },
        { label: 'Открыть…', accelerator: 'CmdOrCtrl+O', click: () => mainWindow?.webContents.send('desktop-command', 'open') },
        { label: 'Сохранить как…', accelerator: 'CmdOrCtrl+Shift+S', click: () => mainWindow?.webContents.send('desktop-command', 'save-as') },
        { type: 'separator' },
        { role: 'quit', label: 'Выйти' }
      ]
    },
    {
      label: 'Вид', submenu: [
        { role: 'reload', label: 'Перезагрузить интерфейс' },
        { role: 'togglefullscreen', label: 'Полный экран', accelerator: 'F11' },
        { role: 'toggleDevTools', label: 'Инструменты разработчика' }
      ]
    },
    {
      label: 'Стол', submenu: [
        { label: 'Экспедиция', accelerator: 'CmdOrCtrl+1', click: () => mainWindow?.webContents.send('desktop-command', 'view-expedition') },
        { label: 'Бой', accelerator: 'CmdOrCtrl+2', click: () => mainWindow?.webContents.send('desktop-command', 'view-combat') },
        { label: 'Персонажи', accelerator: 'CmdOrCtrl+3', click: () => mainWindow?.webContents.send('desktop-command', 'view-characters') },
        { label: 'Сцена', accelerator: 'CmdOrCtrl+4', click: () => mainWindow?.webContents.send('desktop-command', 'view-scene') },
        { label: 'Бастион', accelerator: 'CmdOrCtrl+5', click: () => mainWindow?.webContents.send('desktop-command', 'view-hub') },
        { label: 'Медиатека', accelerator: 'CmdOrCtrl+6', click: () => mainWindow?.webContents.send('desktop-command', 'view-library') },
        { label: 'Конструктор', accelerator: 'CmdOrCtrl+7', click: () => mainWindow?.webContents.send('desktop-command', 'view-workshop') }
      ]
    }
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

ipcMain.handle('save-campaign', async (_event, payload) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    title: 'Сохранить кампанию GrimDice',
    defaultPath: payload.suggestedName || 'campaign.grimdice.json',
    filters: [{ name: 'Кампания GrimDice', extensions: ['json'] }]
  });
  if (result.canceled || !result.filePath) return { canceled: true };
  const { writeFile } = require('node:fs/promises');
  await writeFile(result.filePath, payload.data, 'utf8');
  return { canceled: false, path: result.filePath };
});

ipcMain.handle('open-campaign', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Открыть кампанию GrimDice', properties: ['openFile'],
    filters: [{ name: 'Кампания GrimDice', extensions: ['json'] }]
  });
  if (result.canceled || !result.filePaths[0]) return { canceled: true };
  const { readFile } = require('node:fs/promises');
  return { canceled: false, path: result.filePaths[0], data: await readFile(result.filePaths[0], 'utf8') };
});

ipcMain.handle('network-info', () => ({ addresses: localAddresses(), platform: process.platform, port: localPort }));

app.whenReady().then(async () => {
  installMenu();
  await createWindow();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  try { localServer?.close(); } catch {}
});
