# Выпуск «Драконьей Саги» Desktop

## Требования

- чистая ветка `main`;
- Node.js `>=22.12.0`;
- версия в `package.json` и `package-lock.json` совпадает;
- полный `npm test` проходит;
- тег имеет вид `v2.2.0` и точно совпадает с версией пакета.

## Локальная проверка

```bash
npm ci
npm test
npm audit --omit=dev
npm run pack
```

`npm run pack` создаёт распакованную сборку текущей платформы. Полные кроссплатформенные артефакты собирает GitHub Actions на нативных runner-ах.

## Публикация 2.2.0

```bash
git add -A
git commit -m "Release Dragon Saga Desktop 2.2.0"
git push origin main
git tag v2.2.0
git push origin v2.2.0
```

Workflow **Build and publish installers**:

1. повторно запускает тесты;
2. проверяет соответствие тега версии;
3. собирает Windows NSIS x64;
4. собирает Linux AppImage и DEB x64;
5. собирает macOS universal DMG и updater ZIP;
6. формирует `SHA256SUMS.txt`;
7. создаёт GitHub Release и загружает updater metadata.

Можно запустить workflow вручную и указать `v2.2.0`.

## Если получен единый ZIP с исходниками

1. Распакуйте ZIP локально. Сам ZIP не нужно добавлять в репозиторий как один файл: GitHub Actions видит только распакованные исходники.
2. Замените содержимое ветки `main` файлами из архива, обязательно сохранив скрытую папку `.github/workflows`.
3. Зафиксируйте и отправьте изменения в `main` через GitHub Desktop, Git или **Add file → Upload files**.
4. Откройте **Actions → Build and publish installers → Run workflow**.
5. В поле `tag` укажите `v2.2.0`, `prerelease` оставьте выключенным и запустите сборку.
6. После завершения Windows, Linux и macOS задания установщики появятся в автоматически созданном GitHub Release `v2.2.0`.

Если тег `v2.2.0` уже существует от неудачной попытки, удалите старый тег/черновик релиза перед повторным выпуском или увеличьте версию во всех package-файлах.

## Подпись

Сейчас `CSC_IDENTITY_AUTO_DISCOVERY=false`, а macOS identity не задана: сборки намеренно неподписанные. В дальнейшем Windows code signing и Apple Developer ID/notarization подключаются через GitHub Secrets без изменения форматов установщиков.

## Автообновление

Electron использует `electron-updater` и GitHub Releases репозитория `Meedazzz/DND`. Для обновления должны быть опубликованы установщики, blockmap и `latest*.yml`, созданные одной версией electron-builder.
