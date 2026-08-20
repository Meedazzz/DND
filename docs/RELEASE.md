# Выпуск GrimDice Desktop

## Матрица артефактов

| ОС | Runner | Полный установщик | Дополнительный формат | Автообновление |
|---|---|---|---|---|
| Windows x64 | `windows-2025` | NSIS Setup `.exe` | — | `latest.yml` + blockmap |
| Linux x64 | `ubuntu-24.04` | `.deb` | `.AppImage` | `latest-linux.yml`; автоматическое обновление AppImage |
| macOS universal | `macos-15` | `.dmg` | `.zip` | `latest-mac.yml` + ZIP blockmap |

ZIP на macOS не дублирует установщик: он нужен `electron-updater` для доставки новой версии. Workflow публикует также `SHA256SUMS.txt`. Portable Windows-версия намеренно удалена, чтобы не поддерживать лишний канал установки.

## Обычный выпуск

1. Обновить `version` одновременно в `package.json` и `package-lock.json`:
   ```bash
   npm version 2.1.0 --no-git-tag-version
   ```
2. Выполнить `npm ci`, `npm test` и `npm audit --omit=dev`.
3. Отправить коммит в `main`.
4. Создать и отправить тег, в точности совпадающий с версией: `v2.1.0`.
5. Workflow **Build and publish installers** создаст GitHub Release. Его можно запустить и вручную, указав тот же тег.
6. Проверить три updater-манифеста, все установщики и SHA-256 manifest в Release.

Workflow останавливается, если тег не совпадает с версией пакета, тесты не проходят или хотя бы один ожидаемый артефакт отсутствует.

## Обновления

`electron-updater` использует публичные Releases репозитория `Meedazzz/DND`. Проверка выполняется только в packaged-приложении:

- через 12 секунд после запуска;
- затем каждые 6 часов;
- вручную из бокового меню или меню Electron.

Загрузка начинается по команде пользователя. После загрузки можно сразу перезапустить приложение либо установить обновление при следующем выходе. Предрелизы отключены.

## Неподписанный этап

Текущая конфигурация намеренно не ищет сертификаты (`CSC_IDENTITY_AUTO_DISCOVERY=false`, macOS `identity: null`). Поэтому Windows SmartScreen и macOS Gatekeeper могут показать предупреждение. Файлы остаются полноценными установщиками, но пользователю следует сверять SHA-256.

## Подписание позже

Не коммитить сертификаты и пароли в репозиторий. Добавить их как GitHub Actions Secrets:

- Windows: сертификат PFX и пароль либо облачный signing provider;
- macOS: Developer ID Application, пароль, `APPLE_ID`, app-specific password и `APPLE_TEAM_ID` для notarization.

После подключения секретов убрать `identity: null` и `CSC_IDENTITY_AUTO_DISCOVERY=false` для release job. Имена артефактов, updater provider и схема версий меняться не должны — так сохраняется совместимость обновлений.

## Локальная сборка

```bash
npm run pack:windows
npm run pack:linux
npm run pack:mac
```

Собирать установщик следует на соответствующей ОС. Для финального релиза каноническими считаются результаты нативных GitHub runners, а не cross-build.
