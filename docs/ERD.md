# ERD & Kontrak Data — Dibuang Sayang

Status: **dikunci** (2026-09-27). Perubahan setelah dikunci wajib lewat GitHub Issue, dan hanya
pemilik app terkait yang membuat migrasinya.

## Entitas

### Restaurant (app `food`, PIC Kapitra)
| Field | Tipe | Keterangan |
| --- | --- | --- |
| id | PK | |
| owner | FK -> accounts.User | mitra pemilik (role=partner) |
| nama | CharField | |
| alamat | CharField | |
| lat | DecimalField | |
| lng | DecimalField | |
| jam_buka | TimeField | |
| jam_tutup | TimeField | |
| is_active | BooleanField (default True) | soft-delete flag |
| dibuat_pada | DateTimeField (auto_now_add) | |

### SurpriseBox (app `food`, PIC Kapitra)
| Field | Tipe | Keterangan |
| --- | --- | --- |
| id | PK | |
| restaurant | FK -> food.Restaurant | |
| nama_paket | CharField | |
| harga_normal | DecimalField | |
| harga_diskon | DecimalField | |
| stok | PositiveIntegerField | |
| pickup_start | DateTimeField | |
| pickup_end | DateTimeField | |
| is_active | BooleanField (default True) | soft-delete flag |

### Order (app `order`, PIC Dyah)
| Field | Tipe | Keterangan |
| --- | --- | --- |
| id | PK | |
| pembeli | FK -> accounts.User | |
| surprise_box | FK -> food.SurpriseBox | |
| jumlah | PositiveIntegerField | |
| status | CharField (choices: pending, confirmed, completed, cancelled) | |
| kode_pickup | CharField (unique) | |
| dibuat_pada | DateTimeField (auto_now_add) | |

### Review (app `review`, PIC Khansa)
| Field | Tipe | Keterangan |
| --- | --- | --- |
| id | PK | |
| order | OneToOneField -> order.Order | satu review per order |
| rating | PositiveSmallIntegerField (1-5) | |
| teks | TextField | |
| dibuat_pada | DateTimeField (auto_now_add) | |
| is_active | BooleanField (default True) | soft-delete flag |

## Relasi
- `Restaurant` 1—N `SurpriseBox`
- `SurpriseBox` 1—N `Order`
- `Order` 1—1 `Review`
- `accounts.User` 1—N `Order` (sebagai pembeli), 1—N `Restaurant` (sebagai mitra pemilik)

## Aturan
- Satu app = satu pemilik model/migrasi. Jangan edit model atau migrasi app modul lain.
- Perubahan kontrak di atas hanya lewat GitHub Issue, disetujui, baru pemilik app membuat migrasinya.
- Selama modul food/order/review belum punya model sendiri, gunakan data dummy di
  [`fixtures/dummy_data.json`](../fixtures/dummy_data.json) yang mengikuti kontrak field ini.
