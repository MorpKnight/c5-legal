# P0.2 CSV Audit

## Outcome

Input berhasil dibaca tanpa mengubah file sumber. Duplikat persis dipisahkan secara deterministik, record yang belum terverifikasi dikarantina, dan teks retrieval dibuat terpisah dari definisi sumber.

Hasil ini adalah audit teknis. Status `candidate_secondary_source` bukan verifikasi hukum karena URL sumber saat ini masih merupakan aggregator sekunder.

## Input integrity

- Input path: `data/raw/kamus_hukum.csv`
- SHA-256: `b5ef1135091837f0fa1ee115a6d03cb887a8dae0afd0614b4c1c5f7f680122d4`
- Size: 1,520,259 byte
- Raw records: 3,825
- Raw input unchanged after processing: `true`

## Deduplication and senses

- Exact duplicate rows removed: 677
- Unique records after exact dedupe: 3,148
- Unique normalized terms: 3,146
- Duplicate term groups in raw input: 604
- Raw records participating in duplicate term groups: 1,283
- Terms with more than one distinct sense/source record: 2
- Curated candidate records: 3,133
- Quarantined unique records: 15
- Raw rows represented by quarantine: 20

## Retrieval text

- Prefix containing the answer term removed: 3,135
- Prefix not removed: 13
- Definition length minimum: 24 characters
- Definition length median: 198 characters
- Definition length p90: 331 characters
- Definition length maximum: 793 characters

### Prefix mismatch requiring review

- Anak Perusahaan BUMN
- Cadangan Strategis Energi
- Eksploitasi Minyak dan Gas Bumi
- Eksplorasi Minyak dan Gas Bumi
- Hapus Buku Piutang Pajak
- Kantor Cabang Bank
- Komponen Cadangan Pertahanan Negara
- Komponen Pendukung Pertahanan Negara
- Komponen Utama Pertahanan Negara
- Lelang Noneksekusi Sukarela Terjadwal Khusus
- Niaga Minyak dan Gas Bumi
- Peleburan Perseroan Terbatas
- Pengambilalihan Perseroan Terbatas

## Missing fields

- `istilah`: 0
- `pengertian`: 0
- `undang_undang`: 0
- `uu`: 11
- `url`: 0
- `status`: 0

## Source status

- `OK`: 3814
- `UU/JUDUL TIDAK DITEMUKAN`: 11

## Source hosts

- `paralegal.id`: 3148

## Quarantine reasons

- `source_unverified`: 9
- `unparseable_regulation_identity`: 6

### Quarantined terms

- Eksistensi Keluarga — `source_unverified`
- Interaksi Keluarga — `source_unverified`
- Kelentingan Keluarga — `source_unverified`
- Keluarga Tangguh — `source_unverified`
- Kerentanan Keluarga — `source_unverified`
- Kesejahteraan Keluarga — `source_unverified`
- Ketahanan Keluarga — `source_unverified`
- Ketahanan Nasional — `source_unverified`
- Krisis Keluarga — `source_unverified`
- Grosse Akta — `unparseable_regulation_identity`
- Hortikultura — `unparseable_regulation_identity`
- Kependudukan — `unparseable_regulation_identity`
- Kurator — `unparseable_regulation_identity`
- Maklumat Pelayanan — `unparseable_regulation_identity`
- Pohon Perumahan — `unparseable_regulation_identity`

## Terms with multiple distinct sense/source records

- Kode Etik Jurnalistik
- Lembaga Penyedia Layanan Peningkatan Kualitas Keluarga

## Data boundary

- `source_definition` mempertahankan teks sumber setelah normalisasi Unicode dan whitespace konservatif.
- `retrieval_text` hanya menghapus awalan istilah yang membocorkan jawaban.
- Record non-`OK`, tanpa judul regulasi, atau dengan identitas regulasi yang tidak dapat diurai dipisahkan dari kandidat utama.
- Tidak ada record yang diberi status `verified` pada P0.2.
- Pencocokan ke sumber resmi dan status keberlakuan regulasi adalah tahap berikutnya.
