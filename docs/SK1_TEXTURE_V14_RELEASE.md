# Moonlight SK1 Texture v14 — 4K HDR / low-latency

**Экспериментальная сборка для Ugoos SK1 (Amlogic S928X-K, Android 14).**  
База: [Moonlight V+](https://github.com/qiin2333/moonlight-vplus) 12.13.3.

> **Полевое тестирование владельца Ugoos SK1:** HEVC-стриминг в **4K с HDR** работает плавно, с **субъективно минимальной задержкой управления**. Предыдущие версии Moonlight на этом устройстве испытывали сильные рывки HEVC. Результат подтверждён пользователем на конкретной приставке; независимого измерения задержки в миллисекундах и проверки других моделей нет.

## Что нового и зачем нужен этот APK

После длительных испытаний аппаратного HEVC-декодера Amlogic и путей отображения `SurfaceView` / `TextureView` собрана новая диагностическая версия **v14**. По сравнению с присланной v13 содержимое APK изменилось (манифест и DEX-код). Точный diff исходного Kotlin-кода пока недоступен; поэтому **название `crop-test` не считается доказательством какой-либо конкретной реализации или исправления обрезки**.

Рабочая цель: сохранить аппаратное декодирование HEVC и достичь плавного вывода 4K HDR на Ugoos SK1 с низкой задержкой. Эта цель, **по результату тестирования владельца**, достигнута на его устройстве.

## APK — проверенные данные

| Поле | Значение |
| --- | --- |
| Имя файла | `Moonlight-SK1-Texture-v14-crop-test-noautoupdate.apk` |
| Имя приложения | `Moonlight SK1 Texture` |
| Идентификатор пакета | `com.limelight.vplus_sk1texture` |
| `versionName` | `12.13.3-sk1texture14-crop-test-noautoupdate` |
| `versionCode` | `121303014` |
| Минимальный Android | 5.1 (API 22) |
| `targetSdkVersion` | 35 |
| ABI | ARM64 (`arm64-v8a`) и ARMv7 (`armeabi-v7a`) |
| Размер | 37 916 510 байт (~36.16 MiB) |
| Подпись | `CN=SK1 Texture Diagnostic` |
| Debuggable | Да (`android:debuggable=true`) |
| Контроль архива | ZIP CRC OK (проверен) |

### SHA-256 APK

```text
aea9fb5a6661c90b6dccee462498026eb8310b51e55d9558ae7656020226eedf  Moonlight-SK1-Texture-v14-crop-test-noautoupdate.apk
```

SHA-256 сертификата подписи:

```text
5F:A6:E3:86:3C:B2:83:63:2A:4D:7A:51:13:41:A4:9F:DE:20:4A:61:ED:65:32:4E:E6:4C:70:1F:6F:5F:C2:3E
```

## Установка и совместимость

- `com.limelight.vplus_sk1texture` — **отдельный пакет** от официального Moonlight и стандартного Moonlight V+. Его можно установить параллельно с ними.
- Сборка v14 имеет **тот же package ID и сертификат**, что и переданная ранее v13, но больший `versionCode` (121303014 вместо 121303013). Android должен разрешать установку v14 поверх v13 без удаления данных, при отсутствии иных ограничений устройства.
- Сборка помечена как `debuggable`: использовать для диагностики и личного тестирования, **не считать проверенной безопасной стабильной версией для всех устройств**.
- Суффикс `noautoupdate` в имени **не является доказательством** отсутствия кода проверки обновлений. В манифесте присутствует `UpdateDownloadReceiver`; поведение обновлений отдельно не проверено.
- Предполагаемая область применения — **Ugoos SK1 / Amlogic S928X-K**. Успех на других Amlogic и Android TV не подтверждён.

## Проверенный сценарий

| Параметр | Результат |
| --- | --- |
| Приставка | Ugoos SK1, Android 14 |
| Источник | Sunshine на ПК |
| Кодек | HEVC |
| Разрешение | 4K |
| HDR | Включён |
| Плавность | Плавно, без прежнего слайд-шоу — **со слов тестировавшего владельца** |
| Задержка | Субъективно минимальная — **без измеренного значения в миллисекундах** |

## Публикация: важно

**Точный исходный код v14 отсутствует в текущей `master`-ветке.** Более ранний [PR #1](https://github.com/DHBender/moonlight-vplus_UGOOS_SK1/pull/1) содержит диагностический патч TextureView, но **не является подтверждённым исходником присланного v14 APK**. Не нужно утверждать обратное.

Проект основан на Moonlight V+ (GPLv3), поэтому при распространении APK важно предоставить соответствующие версии исходного кода и инструкцию сборки. Документ описывает переданный пользователем APK, **не заявляя, что он воспроизводимо собран из имеющейся ветки**.

### Предложение по GitHub Release

- **Tag:** `sk1-texture-v14`.
- **Title:** `Moonlight SK1 Texture v14 — tested 4K HDR HEVC (Ugoos SK1)`.
- **Pre-release:** да.
- **Asset:** `Moonlight-SK1-Texture-v14-crop-test-noautoupdate.apk`.
- **Source:** добавить точные исходники v14 или надлежащий пакет соответствующего исходного кода.

Не создавать общедоступный релиз с обещанием воспроизводимой сборки до выверки соответствующего исходного кода.

---

**English summary:** SK1-specific experimental Moonlight V+ Android APK, tested by its owner on Ugoos SK1 / Amlogic S928X-K with smooth HEVC 4K HDR playback and subjectively very low input latency. `versionCode=121303014`, package `com.limelight.vplus_sk1texture`, Android API 22+. Signed with the same certificate as the supplied v13. APK is debuggable; source parity is not yet verified and wider device compatibility is unknown.
