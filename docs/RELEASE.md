# Выпуск Python-версии

## Локальная проверка

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m compileall -q dragon_saga main.py
pyinstaller --noconfirm --clean --windowed --name DragonSaga main.py
```

## GitHub Actions

1. Загрузите распакованное содержимое исходного ZIP в ветку `main`, включая скрытую папку `.github`.
2. Откройте **Actions → Build Dragon Saga Python**.
3. Запустите workflow вручную или создайте тег `v5.1.0`.
4. Windows, Linux и macOS задания сформируют установочные артефакты (ресурсные арт-заглушки упаковываются через `--add-data`).
5. При теге `v5.1.0` workflow создаст GitHub Release и приложит SHA-256.

Сборки пока не подписываются. Windows SmartScreen и macOS Gatekeeper поэтому могут показать стандартное предупреждение.
