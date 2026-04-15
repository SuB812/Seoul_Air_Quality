# MyStore Analytics — Chinook 음반 매출 분석 대시보드

Chinook 음반 스토어 데이터를 기반으로 한 Streamlit 대시보드입니다.  
매출 분석, 비즈니스 인사이트 도출, 고객 관리 기능을 제공합니다.

---

## 실행 방법

```bash
pip install streamlit pandas plotly numpy
streamlit run app.py
```

---

## 대시보드 구성

| 페이지 | 설명 |
|--------|------|
| 홈 | 태그 선택 → 추천 포트폴리오 카드 표시 |
| 어디에 팔까? | 국가 × 장르 교차 분석, 지역별 납품 전략 |
| 무엇을 팔까? | 아티스트별 매출·판매량·국가 분포 |
| 언제 팔까? | 월별 시즌 패턴 + 선형회귀 매출 예측 |
| 영업사원 포트폴리오 | 장르 집중도·매출 안정성·고객 다양성 |
| 아티스트 충성도 | 반복 구매 비율 기반 팬덤 강도 측정 |
| 장르 시즌 패턴 | 계절성 지수(SI)·변동계수(CV) 분석 |
| 고객 관리 | 고객 조회·추가·수정·삭제 |
| 사원 현황 | 직원 정보 및 담당 매출 성과 |

---

## 비즈니스 인사이트

### 인사이트 1 — 아티스트 충성도 (반복 구매 분석)

**충성도 정의:** 동일 아티스트를 서로 다른 시점(Invoice)에서 2회 이상 구매한 고객 비율 (%)

- 충성도 1위 아티스트는 **The Office (16.7%)** 이며, 전체적으로 반복 구매가 발생한 아티스트는 소수에 불과함
- 국가별로는 **Czech Republic** 에서 아티스트 편중 현상이 가장 뚜렷하게 나타나며 평균 충성도가 가장 높음 (16.7%)
- 반면 **Brazil, Canada, France** 등에서는 반복 구매가 관찰되지 않아 충성도 파악이 어려움
- **전략적 시사점:** 충성도가 높은 아티스트는 팬층이 탄탄하므로, Czech Republic 등 충성도 높은 국가에 해당 아티스트 음반을 집중 납품하는 전략이 효과적

---

### 인사이트 2 — 장르별 시즌 패턴 (계절성 분석)

**측정 지표:**
- 계절성 지수(SI) = 해당 월 매출 ÷ 전체 월 평균 매출 (SI > 1.2: 성수기, SI < 0.8: 비수기)
- 변동계수(CV) = 월별 매출 표준편차 ÷ 평균 × 100 (높을수록 시즌 편차 큼)

- **Comedy, R&B/Soul, Sci Fi & Fantasy, Bossa Nova, Blues, Jazz, Pop** 장르는 시즌 편차가 크며, 특히 **Comedy** 의 성수기는 **9월** (CV 111.1%)
- 반면 **Rock And Roll, Science Fiction, Latin** 장르는 연중 매출이 안정적 (CV 40% 미만)
- **전략적 시사점:** 시즌 민감도가 높은 장르는 성수기 전월 재고 확보가 중요하며, 안정 장르는 연중 균등 발주 전략이 적합

---

### 인사이트 3 — 영업사원 포트폴리오 분석

**측정 지표:** 장르별 매출 비중(레이더 차트), 월별 매출 변동계수(CV)

- 총 매출 1위는 **Jane Peacock ($833.04)**
- 레이더 차트 분석 결과 3인 모두 **Rock 중심** 판매 실적을 보이지만 세부 장르 비중에 차이가 있음
  - Jane Peacock: Rock 주력
  - Margaret Park: Rock 주력
  - Steve Johnson: Rock 주력
- 월별 매출 안정성(CV) 기준으로 **Margaret Park** 의 매출이 가장 안정적 (CV: 64.9%)
- **전략적 시사점:** Rock 외 장르 다양화를 통해 특정 시즌 의존도를 낮추고, CV가 높은 담당자에게는 비수기 매출 관리 전략이 필요

---

## SQL 구문 설명

### 1. 인보이스 + 고객 + 직원 JOIN (메인 데이터 로딩)

```sql
SELECT i.InvoiceId, i.CustomerId, i.InvoiceDate,
       i.BillingCountry AS Country, i.Total,
       c.FirstName || ' ' || c.LastName AS CustomerName,
       e.FirstName || ' ' || e.LastName AS SalesRep
FROM invoices i
LEFT JOIN customers c ON i.CustomerId = c.CustomerId
LEFT JOIN employees e ON c.SupportRepId = e.EmployeeId
```

인보이스(invoices), 고객(customers), 직원(employees) 테이블을 LEFT JOIN으로 연결해 매출 분석의 기본 데이터셋을 구성합니다. LEFT JOIN을 사용해 담당 직원이 없는 고객 데이터도 누락 없이 포함합니다.

---

### 2. 판매 아이템 다중 JOIN (장르·아티스트 분석)

```sql
SELECT ii.InvoiceId, ii.Quantity,
       (ii.UnitPrice * ii.Quantity) AS LineTotal,
       g.Name AS Genre, al.Title AS Album, ar.Name AS Artist,
       i.BillingCountry AS Country
FROM invoice_items ii
JOIN tracks t   ON ii.TrackId  = t.TrackId
JOIN genres g   ON t.GenreId   = g.GenreId
JOIN albums al  ON t.AlbumId   = al.AlbumId
JOIN artists ar ON al.ArtistId = ar.ArtistId
JOIN invoices i ON ii.InvoiceId = i.InvoiceId
```

판매 아이템(invoice_items)을 중심으로 트랙·장르·앨범·아티스트·인보이스 5개 테이블을 JOIN해 장르별·아티스트별 매출 분석에 활용합니다. `UnitPrice * Quantity`로 라인별 매출액(LineTotal)을 계산합니다.

---

### 3. 아티스트 충성도 집계 (GROUP BY + COUNT DISTINCT)

```sql
SELECT ar.Name AS Artist, i.BillingCountry AS Country,
       i.CustomerId,
       COUNT(DISTINCT i.InvoiceId) AS InvoiceCount
FROM invoice_items ii
JOIN tracks t   ON ii.TrackId  = t.TrackId
JOIN albums al  ON t.AlbumId   = al.AlbumId
JOIN artists ar ON al.ArtistId = ar.ArtistId
JOIN invoices i ON ii.InvoiceId = i.InvoiceId
WHERE CAST(strftime('%Y', i.InvoiceDate) AS INTEGER) BETWEEN ? AND ?
GROUP BY ar.Name, i.BillingCountry, i.CustomerId
```

고객별로 동일 아티스트를 몇 번의 서로 다른 Invoice에서 구매했는지 집계합니다. `COUNT(DISTINCT InvoiceId)`로 중복 제거 후 구매 횟수를 측정하며, `strftime`으로 연도 필터링을 적용합니다.

---

### 4. 고객 정보 수정 (UPDATE)

```sql
UPDATE customers
SET FirstName=?, LastName=?, Company=?, Address=?,
    City=?, State=?, Country=?, PostalCode=?, Phone=?, Email=?
WHERE CustomerId=?
```

특정 고객의 정보를 수정합니다. `?` 파라미터 바인딩 방식을 사용해 SQL 인젝션 공격을 방지합니다. `WHERE CustomerId=?`로 특정 고객만 업데이트되도록 제한합니다.

---

### 5. 신규 고객 추가 (INSERT)

```sql
INSERT INTO customers
    (FirstName, LastName, Company, Address, City, State,
     Country, PostalCode, Phone, Fax, Email, SupportRepId)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
```

새 고객 레코드를 customers 테이블에 삽입합니다. Fax는 NULL로 고정하고, 나머지 값은 Python에서 파라미터로 전달합니다.

---

### 6. 고객 삭제 — 연쇄 삭제 (DELETE + 서브쿼리)

```sql
-- 1단계: 관련 구매 아이템 삭제
DELETE FROM invoice_items
WHERE InvoiceId IN (
    SELECT InvoiceId FROM invoices WHERE CustomerId = ?
)

-- 2단계: 인보이스 삭제
DELETE FROM invoices WHERE CustomerId = ?

-- 3단계: 고객 삭제
DELETE FROM customers WHERE CustomerId = ?
```

외래키 제약으로 인해 고객 삭제 시 연결된 데이터를 먼저 삭제해야 합니다. `invoice_items → invoices → customers` 순서로 삭제해 참조 무결성을 유지합니다. 서브쿼리를 사용해 해당 고객의 모든 인보이스 아이템을 한 번에 삭제합니다.

---

## 기술 스택

- **Python** — 백엔드 로직
- **Streamlit** — 웹 대시보드 프레임워크
- **Plotly** — 인터랙티브 차트
- **Pandas** — 데이터 처리
- **NumPy** — 선형회귀 예측
- **SQLite** — 데이터베이스 (chinook.db)
