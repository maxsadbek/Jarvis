# 🎙️ JARVIS ovozi (RVC) — to'liq qo'llanma

Bu qo'llanma uch qismdan iborat:

1. **1-qism** — Google Colab'da Jarvis ovoz modelini o'qitish (bulutda, bepul T4 GPU bilan)
2. **2-qism** — Tayyor fayllarni loyihaga joylashtirish
3. **3-qism** — RVC inference'ni `piper_tts.py` ga ulash (mahalliy, GPU'siz ishlaydi)

> **Nega bulutda o'qitamiz?** RVC modelini o'qitish juda og'ir — bu uchun kuchli GPU kerak. Sizning Intel integrallashgan grafika buni uddalay olmaydi. Lekin **tayyor modelni ishlatish (inference) juda yengil** — oddiy protsessorda (CPU) ham tez ishlaydi. Shuning uchun: o'qitish → Colab (bulutda), foydalanish → o'z kompyuteringizda.

---

## 1-qism: Colab'da model o'qitish

### 1.1. Nima kerak bo'ladi?

- **Google hisobi** (Gmail)
- **10-30 daqiqalik Jarvis nutqi** (ovoz namunalari) — qanday olish bo'yicha 1.2 bo'limga qarang
- Internet (o'qitish paytida)

### 1.2. Ovoz namunalarini tayyorlash

Model sifati namunalar sifatiga bog'liq. Ideal namunalar:

| Talab | Tushuntirish |
|---|---|
| **Davomiylik** | Kamida 10 daqiqa, eng yaxshisi 20-30 daqiqa |
| **Tozalik** | Faqat Jarvis ovozi — musiqa, shovqin, qahramonlar suhbati bo'lmasin |
| **Format** | `.wav` fayllar (`.mp3` bo'lsa avval `.wav` ga o'tkazing) |

**Namunalarni qayerdan olish mumkin?**

- *Iron Man* filmlari (1-3) va *Avengers* filmlaridagi JARVIS dialoglari — filmdan audio olish mumkin.
- Film audiosida musiqa va boshqa ovozlar bor — ularni olib tashlash uchun **vocal separator** ishlating (bepul onlayn: [vocalremover.org](https://vocalremover.org), yoki UVR5 dasturi). Faqat nutq qolishi kerak.
- Namunalar har xil bo'lishi yaxshi: qisqa jumlalar, turli intonatsiya, hatto "Jarvis" so'zi aytilgan joylar.

**Fayllarni yuklash:** Google Drive'da `MyDrive/Jarvis_Dataset` papkasini yarating va hamma `.wav` fayllarni ichiga tashlang.

### 1.3. Notebook'ni Colab'da ochish

1. [colab.research.google.com](https://colab.research.google.com) saytiga kiring (Google hisobingiz bilan).
2. `File` → `Upload notebook` → kompyuteringizdagi `rvc_training/RVC_Jarvis_Training.ipynb` faylini tanlang.

### 1.4. T4 GPU'ni yoqish

Yuqori menyu: **Runtime → Change runtime type → Hardware accelerator: T4 GPU → Save**.

### 1.5. Hujayralarni tartib bilan ishga tushirish

Notebook — bu "hujayralar" (maydonchalar) ketma-ketligi. Har bir hujayraning chap tomonida ▶ tugma bor. **Yuqoridan pastga, bittadan bosing** va bittasi tugashini kuting:

| # | Hujayra | Nima qiladi | Vaqt |
|---|---|---|---|
| 1 | GPU tekshirish | GPU borligini ko'rsatadi | 1 soniya |
| 2 | Drive ulash | Google hisobingizni ulaydi (ruxsat so'raydi — Allow) | 1 daqiqa |
| 3 | Applio o'rnatish | Barcha kerakli dasturlarni o'rnatadi | 5-10 daqiqa |
| 4 | Model parametrlari | Model nomi va sozlamalarni belgilaydi | 1 soniya |
| 5 | 1-qadam: qayta ishlash | Namunalarni bo'laklarga bo'ladi | 2-5 daqiqa |
| 6 | 2-qadam: xususiyatlar | Ovoz xususiyatlarini ajratadi | 10-30 daqiqa |
| 7 | 3-qadam: index | Index fayl yaratadi | 1-3 daqiqa |
| 8 | 4-qadam: o'qitish | **Modelni o'qitadi** | **1-3 soat** |
| 9 | 5-qadam: saqlash | `jarvis.pth` va `jarvis.index` ni Drive'ga yozadi | 1 daqiqa |

> 💡 Har bir hujayra tugagach yonida ✅ belgi (yoki o'sish belgisi) paydo bo'ladi. Agar ❌ xato chiqsa — quyidagi "Muammolar" bo'limiga qarang.

### 1.6. O'qitish paytida nima qilish kerak?

- **Brauzer yorlig'ini yopmang** — ekran o'chsa yoki tab yopilsa Colab to'xtab qolishi mumkin.
- O'qitishda chiqadigan raqamlar: `epoch` (nechanchi davr) va `loss` (xato ko'rsatkichi). Loss kamayishi — normal holat.
- Kompyuteringizdan foydalanish mumkin, faqat brauzer ochiq qolsin.

### 1.7. Tayyor modelni yuklab olish

1. Google Drive → `MyDrive/ApplioExported/jarvis/` papkasini oching.
2. `jarvis.pth` va `jarvis.index` fayllarini kompyuteringizga yuklab oling (Drive'da faylni o'ng tugma → **Download**).
3. `jarvis_backup.zip` kerak emas — o'chirib tashlashingiz mumkin (bu faqat zaxira).

### 1.8. Muammolar va yechimlari

| Muammo | Yechim |
|---|---|
| "CUDA out of memory" xatosi | 4-qadamda `batch_size` ni **8 → 4** ga kamaytiring va qayta ishga tushiring |
| "Ovoz fayli topilmadi" | Namunalarni Drive'dagi `Jarvis_Dataset` papkasiga qo'yganingizni tekshiring |
| Colab uzilib qoldi (vaqt o'tdi) | Qaytadan oching, 1-2-hujayralarni ishga tushiring (Applio o'rnatilgan) va o'qitishni qayta boshlang. Eski natija `jarvis_backup.zip` da saqlanib qolgan |
| Ovoz sifatı yaxshi emas | Ko'proq/toza namuna qo'shing va `total_epoch` ni 400-800 ga oshiring |
| Dataset juda kichik | 10 daqiqadan kam bo'lsa, model yaxshi chiqmaydi — namuna to'plang |

---

## 2-qism: Fayllarni loyihaga joylashtirish

1. Loyiha ildizida `data/models/rvc/jarvis/` papkasini yarating:

```
data/
└── models/
    └── rvc/
        └── jarvis/
            ├── jarvis.pth      ← Colab'dan yuklab olingan fayl
            └── jarvis.index    ← Colab'dan yuklab olingan fayl
```

2. `jarvis.pth` va `jarvis.index` fayllarini shu papkaga qo'ying.

Shu bilan tayyor — 3-qismga o'ting.

---

## 3-qism: RVC inference'ni loyihaga ulash

Bu qismni men (assistent) **allaqachon kodlab qo'ydim** — sizga faqat 3 ta narsa qoladi: Python 3.10 muhitini yaratish, `rvc-python` o'rnatish va `.env` da yoqish.

### 3.1. Nima qo'shildi?

| Fayl | Vazifasi |
|---|---|
| `backend/app/text_to_speech/rvc_worker.py` | Yangi fayl. RVC conversion'ni bajaradigan kichik "ishchi" dastur (aloqada jarayon — model bir marta yuklanadi va keyin tez ishlaydi) |
| `backend/app/text_to_speech/piper_tts.py` | RVC post-processing qo'shildi: Piper matnni nutqqa aylantirgach, ovoz RVC orqali Jarvis ovoziga o'zgartiriladi |
| `backend/app/config.py` | RVC sozlamalari qo'shildi (pastga qarang) |
| `backend/requirements-rvc.txt` | RVC kutubxonasi ro'yxati (alohida muhitga o'rnatiladi) |

**Ishlash tartibi:**

```
matn → Piper TTS (nutq hosil qiladi) → RVC (Jarvis ovoziga o'zgartiradi) → frontend'ga audio
```

### 3.2. Nega alohida Python 3.10 muhiti kerak? (qisqacha)

`rvc-python` kutubxonasi eski `numpy` versiyasini talab qiladi (`numpy<=1.23.5`), u esa **Python 3.11 va undan yangi versiyalar bilan ishlamaydi**. Loyihangiz backend'i Python 3.11+ ishlatadi. Shuning uchun RVC uchun **alohida Python 3.10 muhiti** yaratamiz — ikkalasi bir-biriga xalaqit qilmaydi.

### 3.3. Python 3.10 muhitini yaratish (Windows)

1. **Python 3.10 o'rnatilganligini tekshiring.** Ochiq terminal (yoki VS Code terminali):
   ```
   py -3.10 --version
   ```
   Agar xato chiqsa — [python.org/downloads](https://www.python.org/downloads/) dan **Python 3.10** ni yuklab o'rnating (o'rnatishda "Add to PATH" belgisini qo'ying).

2. Loyiha ildizida alohida muhit yarating:
   ```
   py -3.10 -m venv rvc-venv
   ```

3. Muhitni faollashtiring:
   ```
   rvc-venv\Scripts\activate
   ```

4. RVC kutubxonasini o'rnating (faqat CPU — sizga GPU shart emas):
   ```
   pip install -r backend\requirements-rvc.txt
   ```
   Bu taxminan 1-2 daqiqa davom etadi (torch va boshqa kutubxonalar). Birinchi ishga tushirishda `rvc-python` avtomatik ravishda asosiy modellarni (hubert, rmvpe — jami ~500 MB) yuklab oladi, shuning uchun birinchi marta internet kerak.

### 3.4. `.env` faylida RVC'ni yoqish

Loyiha ildizidagi `.env` faylini oching va quyidagilarni qo'shing:

```ini
# --- RVC (Jarvis ovozi) ---
RVC_ENABLED=true
RVC_MODEL_DIR=data/models/rvc
RVC_MODEL_NAME=jarvis
RVC_PYTHON_PATH=rvc-venv\Scripts\python.exe
```

> `RVC_PYTHON_PATH` — bu 3.3-qadamda yaratilgan muhitdagi `python.exe` manzili. Agar muhitni boshqa papkada yaratgan bo'lsangiz, to'liq manzilni yozing, masalan: `C:\Users\Maxsadbek\Desktop\Jarvis\rvc-venv\Scripts\python.exe`.

Qo'shimcha sifat sozlamalari (ixtiyoriy):

```ini
RVC_INDEX_RATE=0.7      # 0-1. Index qanchalik kuchli ta'sir qilsin (0.5-0.8 tavsiya)
RVC_F0_METHOD=harvest   # Ovoz balandligini aniqlash usuli: harvest (tez) | rmvpe (aniqroq, sekinroq)
RVC_F0_UP_KEY=0         # Balandlik siljishi: 0 = o'zgarishsiz
RVC_PROTECT=0.33        # Undosh va nafas tovushlarini himoya qilish
RVC_RMS_MIX_RATE=0.8    # Ovoz balandligi aralashmasi
```

### 3.5. Ishga tushirish va tekshirish

1. Backend'ni odatdagidek ishga tushiring.
2. Server loglarida quyidagi qator paydo bo'lishi kerak:
   ```
   ✓ RVC voice conversion ready (jarvis, worker)
   ```
3. Jarvisga biror narsa ayting yoki yozing — javob endi **Jarvis ovozida** chiqadi.

> **Eslatma:** RVC sozlamada `RVC_ENABLED=false` bo'lsa (yoki model papkasi topilmasa), tizim odatdagidek Piper ovozi bilan ishlaydi — hech narsa buzilmaydi. RVC faqat qo'shimcha qatlam.

### 3.6. Tez-tez so'raladigan savollar

**Ovoz Jarvisnikiga o'xshamayapti?**
- `index_rate` ni 0.5 ga tushiring yoki 0.9 ga oshiring va sinab ko'ring.
- `RVC_F0_METHOD=rmvpe` qilib ko'ring (aniqroq, lekin sekinroq).
- Model 200 epoxdan kam o'qitilgan bo'lsa — sifat past bo'ladi.

**"RVC worker javob bermadi" xatosi?**
- `RVC_PYTHON_PATH` to'g'ri ekanini tekshiring (o'sha `python.exe` manzili).
- Terminalda quyidagini sinab ko'ring — xato matni chiqadi:
  ```
  rvc-venv\Scripts\python -c "from rvc_python.infer import RVCInference; print('OK')"
  ```

**Javob biroz kechikib chiqyapti?**
- Normal holat — CPU'da RVC har bir gapga 1-3 soniya qo'shadi. `harvest` usuli eng tezi.

---

## Ilova: papka tuzilishi (yakuniy holat)

```
Jarvis/
├── rvc_training/
│   ├── RVC_Jarvis_Training.ipynb   ← Colab notebook (1-qism)
│   └── QOLLANMA.md                 ← Shu fayl
├── data/models/rvc/jarvis/
│   ├── jarvis.pth                  ← Colab'dan (2-qism)
│   └── jarvis.index                ← Colab'dan (2-qism)
├── rvc-venv/                       ← Python 3.10 muhiti (3-qism)
└── backend/app/text_to_speech/
    ├── piper_tts.py                ← RVC ulangan (avtomatik)
    ├── rvc_worker.py               ← RVC ishchisi (avtomatik)
    └── engine.py
```
