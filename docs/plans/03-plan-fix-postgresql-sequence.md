# 🛠️ Rencana Aksi & Analisis: Perbaikan Tabrakan Sequence PostgreSQL (PWS HTTP 500)

**Penanggung Jawab (PIC)**: Kapitra Fachriza Utomo  
**Modul**: `food` (Food & Restaurant)  
**Tingkat Keparahan**: Critical (HTTP 500 saat penambahan data baru di produksi)  
**Status**: Selesai (Fixed & Tested)  

---

## 🔍 1. Deskripsi Masalah

### Endpoint Terkena Dampak:
- `POST /food/restaurant/create/` (Tambah Restoran Baru)
- `POST /food/restaurant/<id>/box/create/` (Tambah Paket Surprise Box)

### Error Log di Sentry / PWS Console:
```text
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "food_restaurant_pkey"
DETAIL: Key (id)=(1) already exists.
```

---

## 🧠 2. Analisis Akar Masalah (Root Cause)

1. **Pengisian ID Manual pada Seeder**:
   - Skrip `seed_food.py` membaca `fixtures/dummy_data.json` dan memanggil `Restaurant.objects.update_or_create(id=item["id"], ...)` secara manual untuk ID 1 hingga 55 (serta SurpriseBox ID 1 hingga 104).
2. **Karakteristik Sequence PostgreSQL**:
   - Di PostgreSQL, ketika baris baru di-insert dengan nilai Primary Key (`id`) eksplisit, PostgreSQL **tidak otomatis memajukan counter sequence** (`food_restaurant_id_seq` atau `food_surprisebox_id_seq`).
   - Akibatnya, internal sequence counter tetap bernilai `1`.
3. **Pemicu Tabrakan**:
   - Ketika mitra membuat restoran baru via formulir web (`form.save()`), Django tidak menyertakan ID, sehingga PostgreSQL memanggil `nextval('food_restaurant_id_seq')` yang mengembalikan angka `1`.
   - Karena ID `1` sudah ada dari hasil seeding, database melempar `UniqueViolation` yang berujung pada HTTP 500 Internal Server Error.

---

## 🚀 3. Rencana Solusi & Eksekusi

### A. Solusi Cepat (Hotfix Produksi PWS)
Menjalankan sinkronisasi counter sequence secara langsung di server PWS ke nilai maksimum ID saat ini:

```bash
python manage.py shell --settings=config.settings.prod -c "from django.db import connection; cursor = connection.cursor(); cursor.execute(\"SELECT setval(pg_get_serial_sequence('food_restaurant', 'id'), coalesce(max(id), 1)) FROM food_restaurant;\"); cursor.execute(\"SELECT setval(pg_get_serial_sequence('food_surprisebox', 'id'), coalesce(max(id), 1)) FROM food_surprisebox;\"); print('Sequence synced successfully!')"
```

---

### B. Solusi Permanen di Kode (Codebase Fix)

1. **Otomatisasi di `food/management/commands/seed_food.py`**:
   - Menambahkan pemanggilan `connection.ops.sequence_reset_sql(no_style(), [Restaurant, SurpriseBox])` pada akhir proses seeding.
   - Bersifat database-agnostic: otomatis mereset sequence pada PostgreSQL, dan aman tanpa error di SQLite lokal.

2. **Pembuatan Management Command Baru `reset_sequences.py`**:
   - Lokasi: `food/management/commands/reset_sequences.py`
   - Memungkinkan developer atau DevOps mereset sequence kapan saja:
     ```bash
     python manage.py reset_sequences --settings=config.settings.prod
     ```

3. **Penulisan Unit Test di `food/tests.py`**:
   - `test_reset_sequences_command`: Memverifikasi eksekusi aman pada SQLite dev.
   - `test_reset_sequences_command_executes_sql`: Memverifikasi bahwa SQL sequence reset dieksekusi dengan benar ke database cursor.

---

## ✅ 4. Kriteria Keberhasilan
- [x] Endpoint `POST /food/restaurant/create/` berhasil membuat restoran baru (ID berlanjut dari 56, 57, dst.).
- [x] Endpoint `POST /food/restaurant/<id>/box/create/` berhasil membuat paket baru (ID berlanjut dari 105, 106, dst.).
- [x] Seluruh 27 unit test modul food lulus 100% OK.
