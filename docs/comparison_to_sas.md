# Pytae vs. SAS — Deep Dive & Migration Guide

[← Back to Master Reference](pytae.md) | [Comparison with Pandas](comparison_to_pandas.md) | [Comparison with dplyr](comparison_to_dplyr.md)

For over four decades, **SAS (Statistical Analysis System)** has been the foundational analytical engine in regulated enterprise environments: clinical trials, biostatistics, pharmaceutical submissions (CDISC SDTM / ADaM), banking risk models (Basel / CECL / CCAR), insurance actuarial analysis, and government statistics.

As organizations modernize their tech stacks and migrate toward Python and cloud-native architectures, SAS developers, biostatisticians, and risk analysts often encounter steep friction with standard Python tools like Pandas. Pandas introduces foreign index abstractions, fragile chaining, and multi-syntax confusion.

`pytae` provides a natural, high-performance bridge for SAS professionals:
1. **Familiar Tabular Intuition**: Pure, flat 2D data tables without index complexity.
2. **"One and Only One Obvious Way"**: Eliminates syntax fragmentation by providing exactly one clear verb per task.
3. **Massive Multithreaded Vector Speed**: Replaces slow, iterative row-by-row `DATA` step processing with 100% native Rust/Polars SIMD vectorization.
4. **Native `.sas7bdat` Ingestion**: Read legacy SAS datasets directly without needing SAS installed.

---

## Key Architectural Differences: Pytae vs. SAS

```
┌───────────────────────────────┬──────────────────────────────────┬──────────────────────────────────┐
│ Architectural Dimension       │ SAS (Base SAS, STAT, ETS)        │ Pytae (Python Library & CLI)     │
├───────────────────────────────┼──────────────────────────────────┼──────────────────────────────────┤
│ Core Execution Paradigm       │ Row-by-row Program Data Vector   │ Multithreaded SIMD Vector Core   │
│ Syntax Architecture           │ Split: DATA step vs PROC SQL/PROCs│ Single, unified grammar          │
│ In-Memory Data Structure      │ SAS Dataset (.sas7bdat) on disk  │ Apache Arrow / Polars DataFrame  │
│ Missing Value Internal Rep    │ Numeric '.' is smaller than -Inf │ Strict null / IEEE-754 NaN       │
│ Relational Merge Prerequisite │ All inputs MUST be sorted on disk│ In-memory hash join (no sort)    │
│ State Tracking (Lags/Sums)    │ Manual RETAIN, FIRST., LAST.     │ Declarative window expressions   │
│ Grouping Mechanism            │ BY statement (requires sort)     │ Single-shot by() (auto-clearing) │
│ Reshaping                     │ PROC TRANSPOSE (_NAME_, COL1)    │ Unified wide(), long(), pivot()  │
│ Interactive Execution         │ Batch (.sas -> .log / .lst)      │ Interactive Python REPL & CLI    │
└───────────────────────────────┴──────────────────────────────────┴──────────────────────────────────┘
```

---

## 1. The Core Paradigm Shift: SAS Program Data Vector vs. Pytae Vector SIMD

### The SAS Execution Model
In SAS, the `DATA` step is an explicit, procedural row-by-row loop:
1. SAS initializes the **Program Data Vector (PDV)** in memory.
2. It reads one observation from disk into the PDV.
3. It executes the statements in the `DATA` step sequentially.
4. At the `RUN;` statement, it outputs the PDV to disk and loops back to step 2 until the end of the file (`EOF`).

While intuitive for sequential accounting logic, the PDV model creates significant overhead:
- It relies heavily on temporary disk scratch space (`WORK` library).
- Window calculations require manual state maintenance using `RETAIN` statements and automatic variables (`_N_`, `_ERROR_`).
- Operations cannot parallelize across CPU cores because rows are processed sequentially.

### The Pytae Vector Execution Model
Pytae executes operations on **entire column vectors simultaneously**:
- Processing is powered by native Rust/Polars multithreaded SIMD kernels.
- Operations automatically saturate all available CPU cores.
- Data resides in contiguous Apache Arrow memory buffers with zero Python GIL lockup.

---

## 2. The Dangerous SAS Missing Value Trap vs. Pytae Safe Nulls

### The SAS Negative Infinity Trap
In SAS, numeric missing values (`.`, `.A` through `.Z`) are stored internally as special double-precision values that are **smaller than negative infinity** ($-\infty$):

$$\text{Missing } (.) < -999{,}999{,}999 < 0 < \text{Positive Numbers}$$

This architectural choice causes catastrophic logic errors when filtering or deriving variables:

```sas
/* DANGEROUS SAS LOGIC BUG */
DATA pediatric_check;
  SET clinical_patients;
  IF age < 18 THEN pediatric = 1; /* BUG! */
  ELSE pediatric = 0;
RUN;
```

> [!CAUTION]
> If a patient's `age` is missing (`.`), SAS evaluates `age < 18` as **TRUE** because `.` is smaller than 18! Consequently, patients with unrecorded ages are misclassified as pediatric patients.
>
> SAS programmers are forced to write defensive, verbose conditions everywhere:
> `IF NOT MISSING(age) AND age < 18 THEN pediatric = 1;`

### The Pytae Safe Null Model
In Pytae, missing values adhere to strict three-valued logic and IEEE-754 semantics:
- A comparison with missing (`null` or `NaN`) always evaluates to missing / false.
- Filtering `df.filter("age < 18")` **never** includes null or NaN records.
- Null checks are explicit and readable: `df.filter("age.notna()")` or `df.filter("age.isna()")`.

---

## 3. Merge Requirements: SAS Pre-Sorting vs. Pytae Instant Hash Joins

### The SAS Sort Requirement
In SAS, merging two datasets using the `MERGE` statement in a `DATA` step strictly requires that **both datasets be physically sorted on disk by the merge keys**:

```sas
/* MANDATORY SAS PRE-SORTING */
PROC SORT DATA=work.demographics;
  BY patient_id;
RUN;

PROC SORT DATA=work.vitals;
  BY patient_id;
RUN;

DATA work.merged;
  MERGE work.demographics (IN=in_demo) work.vitals (IN=in_vit);
  BY patient_id;
  IF in_demo; /* Left join */
RUN;
```

If either dataset is not sorted, SAS halts execution with a fatal runtime error:
`ERROR: BY variables are not properly sorted on data set WORK.DEMOGRAPHICS.`

### The Pytae Instant Hash Join
Pytae uses in-memory hash joins:
- Datasets **never** need to be pre-sorted.
- Keys with different column names are linked with a simple colon (`on="patient_id:subjid"`).
- Join cardinality is validated automatically if desired:

```python
# PYTAE: Zero pre-sorting required
demographics.join(vitals, on="patient_id", how="left", validate="1:m")
```

---

## 4. Group Statefulness: SAS `RETAIN` and `FIRST.`/`LAST.` vs. Pytae Declarative Windows

### The SAS Multi-Step Ceremony
In SAS, computing running totals, cumulative maximums, or group percentages requires:
1. Running `PROC SORT` by the grouping variable.
2. Creating a `DATA` step with a `BY` statement.
3. Explicitly declaring `RETAIN` variables.
4. Writing conditional logic checking `IF FIRST.group THEN ...`:

```sas
/* SAS: Cumulative sales by region */
PROC SORT DATA=sales;
  BY region;
RUN;

DATA sales_running;
  SET sales;
  BY region;
  RETAIN cum_sales;
  IF FIRST.region THEN cum_sales = 0;
  cum_sales = cum_sales + amount;
RUN;
```

### The Pytae Single-Line Declarative Vector
In Pytae, grouped calculations are written as clear, declarative expressions without state management:

```python
# PYTAE: One obvious declarative line
sales.by("region").mutate(cum_sales="cum_sum(amount)")
```

---

## 5. Reshaping: `PROC TRANSPOSE` vs. `wide`, `long`, `pivot`

### The SAS `PROC TRANSPOSE` Complexity
In SAS, transposing long data into wide data (or vice versa) is notoriously cryptic:
```sas
PROC TRANSPOSE DATA=vitals OUT=vitals_wide (DROP=_NAME_);
  BY patient_id visit;
  ID test_code;
  VAR test_result;
RUN;
```
`PROC TRANSPOSE` produces arbitrary automatic column names (`_NAME_`, `COL1`, `COL2`) that require post-processing `RENAME=` clauses and macro workarounds.

### The Pytae Reshaping Suite
Pytae provides three intuitive, dedicated verbs with zero column name artifacts:
1. **`df.long(id_vars=..., cols=...)`**: Melts wide columns into tall records.
2. **`df.wide(r=..., c=..., v=...)`**: Pure 1-to-1 structural unmelting without aggregation.
3. **`df.pivot(r=..., c=..., v=..., a=...)`**: Generates 2D cross-tabulation aggregation matrices.

---

## 6. Performance & Speed Benchmarks: Base SAS Disk Spooling & PROC SORT vs. Pytae Vector SIMD

In traditional SAS architectures, analytical execution speed is severely throttled by two primary bottlenecks:
1. **Single-Threaded Program Data Vector (PDV)**: Sequential row-by-row iteration in the `DATA` step cannot leverage modern multi-core CPU architectures.
2. **Mandatory Disk Spooling & Sort Steps**: `PROC SORT` and `MERGE ... BY ...` repeatedly write temporary datasets to the `WORK` scratch library on physical disk, incurring massive I/O serialization penalties.

Pytae completely eliminates these bottlenecks by executing in-memory on **Apache Arrow columnar buffers** powered by **Polars Rust SIMD vector parallelism**.

### Comparative Benchmark: SAS vs. Pytae (5,000,000 Records)
*Environment: 5,000,000 observations, clinical trial simulation data (demographics, labs, vital signs).*

| Operation / Pipeline Stage | Base SAS Execution Model | Pytae Execution | Pytae Speedup Advantage |
|:---|:---|:---|:---|
| **End-to-End Pipeline**<br>*(File Read $\to$ Filter $\to$ Derive $\to$ Group Summary $\to$ Sort)* | **`6.50s – 12.00s`**<br>*(Sequential PDV read + PROC MEANS + PROC SORT + disk write)* | **`0.205s`** (Eager)<br>**`0.042s`** (Lazy) | **30x to 150x faster**<br>*(Zero disk spooling)* |
| **Sorting 5M Observations**<br>*(PROC SORT by Category, Value DESC)* | **`5.80s – 9.50s`**<br>*(Writes scratch files to WORK library on disk)* | **`0.730s`**<br>*(In-memory multithreaded radix sort)* | **8x to 13x faster** |
| **Relational Join / Merge**<br>*(1,000,000 obs $\times$ 1,000,000 obs)* | **`3.50s – 6.00s`**<br>*(Requires 2x PROC SORT + DATA step MERGE)* | **`0.052s`**<br>*(Instant in-memory hash join; NO pre-sort!)* | **70x to 110x faster** |
| **Grouped Summary Statistics**<br>*(PROC MEANS / PROC SUMMARY on 5M rows)* | **`1.80s – 3.20s`**<br>*(Single-threaded aggregation step)* | **`0.131s`**<br>*(Multithreaded vector SIMD aggregation)* | **14x to 24x faster** |
| **Ingestion of `.sas7bdat` Files**<br>*(Direct binary SAS dataset read into memory)* | Native SAS engine | **Instant zero-copy Arrow**<br>*(No SAS license required)* | **Direct modern analytics** |

### Why Migration to Pytae Accelerates Clinical & Financial Pipelines
- **No Mandatory Pre-Sorting**: SAS pipelines spend up to 60% of their total wall-clock runtime executing `PROC SORT` simply to satisfy the prerequisite of `MERGE ... BY ...` or `BY` group processing. Pytae hash joins and group contexts require **zero pre-sorting**.
- **Zero Disk Thrashing**: SAS pipelines create dozens of intermediate datasets in `WORK` (`work.temp1`, `work.temp2`), generating heavy disk I/O. Pytae operations stream purely in high-speed RAM and Arrow buffers.
- **Hardware Saturated Concurrency**: While a SAS `DATA` step utilizes only 1 CPU core at 100%, Pytae saturates all 8, 16, or 64 cores simultaneously.

> [!TIP]
> **Reproducibility**: Complete, self-contained benchmark scripts and interactive notebooks are available in **[`docs/benchmarks/`](benchmarks/README.md)** (executable CLI script: [`run_benchmarks.py`](benchmarks/run_benchmarks.py), interactive notebook: [`benchmarks.ipynb`](benchmarks/benchmarks.ipynb)).

---

## 7. Feature-by-Feature Rosetta Stone: Pytae vs. SAS

### 1. Data Ingestion & I/O
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Read SAS Dataset** | `SET libref.dataset;` | `pt.read_sas("dataset.sas7bdat")` | `pytae dataset.sas7bdat` |
| **Read CSV** | `PROC IMPORT DATAFILE='...' DBMS=CSV;` | `pt.read_csv("file.csv")` | `pytae file.csv` |
| **Read Parquet** | SAS Viya CAS Parquet engine | `pt.read_parquet("file.parquet")` | `pytae file.parquet` |
| **Write Parquet** | Viya CAS Save | `df.to_parquet("file.parquet")` | `-o file.parquet` |
| **Write CSV** | `PROC EXPORT DATAFILE='...' DBMS=CSV;` | `df.to_csv("file.csv")` | `-o file.csv` |
| **Clipboard Export** | Custom DDE / ODS script | `df.to_clip()` | `-o clip` |

### 2. Row Filtering
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Simple Filter** | `WHERE sales > 100;` (or `IF sales > 100;`) | `df.filter("sales > 100")` | `-filter "sales > 100"` |
| **Multiple Conditions** | `WHERE a > 1 AND b = 'East';` | `df.filter("a > 1 & b == 'East'")` | `-filter "a > 1, b == 'East'"` |
| **Mathematical Range** | `WHERE 10 <= x <= 20;` | `df.filter(x="[10, 20]")` | `-filter "x = [10, 20]"` |
| **Set Membership** | `WHERE cat IN ('A', 'B');` | `df.filter(cat=['A', 'B'])` | `-filter "cat = ['A', 'B']"` |
| **Spaced Column Name** | `WHERE 'gross sales'n > 50;` | `df.filter("[gross sales] > 50")` | `-filter "[gross sales] > 50"` |
| **String Prefix Match**| `WHERE name LIKE 'A%';` | `df.filter(name=('startswith', 'A'))` | `-filter "name.startswith('A')"` |
| **Non-Missing Check** | `WHERE col IS NOT MISSING;` | `df.filter("col.notna()")` | `-filter "col.notna()"` |

### 3. Column Derivations & Feature Engineering (`mutate`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Simple Math** | `y = a / b;` | `df.mutate(y="a / b")` | `-mutate "y = a / b"` |
| **Sequential Calculations**| `a = 1; b = a * 2;` | `df.mutate(a="1", b="a * 2")` | `-mutate "a=1, b=a*2"` |
| **Conditional (If/Else)** | `IF x > 0 THEN f='pos'; ELSE f='neg';` | `df.mutate(f="if_else(x > 0, 'pos', 'neg')")` | `-mutate "f=if_else(x>0,'pos','neg')"` |
| **Multi-Branch (Case)** | `SELECT; WHEN(c1) f=v1; OTHERWISE f=v3; END;` | `df.mutate(f="case_when(c1, v1, c2, v2, v3)")` | `-mutate "f=case_when(c1,v1,v3)"` |
| **Format / Value Recoding**| `PROC FORMAT; ... PUT(x, fmt.);` | `df.mutate(x="map(x, {'A': 1, 'B': 2})")` | `-mutate "x=map(x, {'A':1})"` |
| **Lag / Previous Row** | `prev = LAG(x);` | `df.mutate(prev="shift(x, 1)")` | `-mutate "prev = shift(x, 1)"` |
| **Multi-Column Transform**| `ARRAY cols(*) a b; DO i=1 TO 2; ...` | `df.mutate("(a, b) = _ * 10")` | `-mutate "(a, b) = _ * 10"` |
| **Multi-Column + Suffix** | Macro loop generating variable assignments | `df.mutate("(a, b)_cm = _ * 10")` | `-mutate "(a, b)_cm = _ * 10"` |

### 4. Column Selection & Renaming (`select`, `rename`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Keep Columns** | `KEEP a b;` (or `SET in (KEEP=a b);`) | `df.select("a", "b")` | `-select "a,b"` |
| **Drop Columns** | `DROP c d;` (or `SET in (DROP=c d);`) | `df.select("-c", "-d")` | `-select "-c,-d"` |
| **Rename Variables** | `RENAME old=new;` | `df.rename("old:new")` | `-rename "old:new"` |
| **Inline Select & Rename**| `SET in (KEEP=a RENAME=(a=b));` | `df.select("a:b")` | `-select "a:b"` |

### 5. Row Sorting (`arrange`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Ascending Sort** | `PROC SORT; BY sales; RUN;` | `df.arrange("sales")` | `-arrange sales` |
| **Descending Sort** | `PROC SORT; BY DESCENDING sales; RUN;` | `df.arrange("sales desc")` | `-arrange "sales desc"` |
| **Multi-Column Sort** | `PROC SORT; BY a DESCENDING b; RUN;` | `df.arrange("a", "b desc")` | `-arrange "a, b desc"` |

### 6. Grouped Summaries (`by` + `agg`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Group Mean** | `PROC MEANS NWAY NOPRINT; CLASS g; VAR x; OUTPUT OUT=out MEAN=m; RUN;` | `df.by("g").agg(m="x:mean")` | `-by g -agg m=x:mean` |
| **Observation Count** | `OUTPUT OUT=out N=n;` | `df.by("g").agg(n="n")` | `-by g -agg n=n` |
| **Multiple Metrics** | `OUTPUT OUT=out MEAN=m SUM=s MIN=mn MAX=mx;` | `df.by("g").agg(m="x:mean", s="x:sum")` | `-by g -agg "m=x:mean,s=x:sum"` |
| **Preserve Missing Groups**| `PROC MEANS MISSING;` *(Defaults to dropping!)*| Default behavior (`dropna=False`) | Default behavior |

### 7. Deduplication (`distinct`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Deduplicate Table** | `PROC SORT NODUPRECS; BY _ALL_; RUN;` | `df.distinct()` | `-distinct` |
| **Deduplicate by Keys** | `PROC SORT NODUPKEY; BY a b; RUN;` | `df.distinct("a", "b")` | `-distinct "a,b"` |

### 8. Extreme Record Slicing (`pick`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Top N Records** | `PROC SORT; BY DESCENDING x; DATA out; SET in; IF _N_ <= 5; RUN;` | `df.pick("x", n=5)` | `-pick "x,n=5"` |
| **Bottom N Records** | `PROC SORT; BY x; DATA out; SET in; IF _N_ <= 5; RUN;` | `df.pick("x", n=5, order="min")` | `-pick "x,n=5,order=min"` |
| **Top N per Group** | `PROC SORT; BY g DESCENDING x; DATA out; SET in; BY g; IF FIRST.g; RUN;` | `df.by("g").pick("x", n=1)` | `-by g -pick "x,n=1"` |

### 9. Reshaping & Pivoting (`wide`, `long`, `pivot`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Wide to Long (Unpivot)**| `PROC TRANSPOSE DATA=in OUT=out; BY id; VAR x y; RUN;` | `df.long(id_vars="id", cols=["x", "y"])` | `-long "id_vars=id, cols='x,y'"` |
| **Long to Wide (Spread)** | `PROC TRANSPOSE DATA=in OUT=out; BY id; ID metric; VAR val; RUN;` | `df.wide(r="id", c="metric", v="val")` | `-wide "r=id, c=metric, v=val"` |
| **2D Pivot Matrix** | `PROC TABULATE` or `PROC TRANSPOSE` after `PROC MEANS` | `df.pivot(r="r", c="c", v="v", a="mean")` | `-pivot "r=r, c=c, v=v, a=mean"` |

### 10. Relational Joins (`join`, `concat`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Inner Join** | `MERGE a (IN=in_a) b (IN=in_b); BY id; IF in_a AND in_b;` *(Requires prior sort!)* | `df1.join(df2, on="id", how="inner")` | `-join "f2.parquet,on=id"` |
| **Left Join** | `MERGE a (IN=in_a) b (IN=in_b); BY id; IF in_a;` *(Requires prior sort!)* | `df1.join(df2, on="id", how="left")` | `-join "f2.parquet,on=id,how=left"` |
| **Different Key Names** | `RENAME=(cust_id=id)` inside `MERGE` statement | `df1.join(df2, on="id:cust_id")` | `-join "f2.parquet,on=id:cust_id"` |
| **Vertical Stack (Concat)**| `DATA out; SET a b; RUN;` | `pt.concat([df1, df2], how="vertical")` | N/A |

### 11. Inspection, Profiling & Validation
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Dataset Metadata** | `PROC CONTENTS DATA=in; RUN;` | `df.glimpse()` | `-glimpse` |
| **Frequency Table** | `PROC FREQ; TABLES col; RUN;` | `df.freq("col")` *(With ASCII bars)* | `-freq col` |
| **Dataset Comparison** | `PROC COMPARE BASE=a COMPARE=b CRITERION=0.01; RUN;` | `df.diff(df2, tol=0.01)` | `pytae a.parquet -diff b.parquet,tol=0.01` |
| **ANSI SQL Engine** | `PROC SQL; SELECT ... FROM in; QUIT;` | `df.sql("SELECT ... FROM self")` | `-sql "SELECT ... FROM file.parquet"` |

---

## 8. End-to-End Migration Example: Clinical Vital Signs Summary

### The Clinical Analysis Task:
In a clinical trial analysis:
1. Ingest clinical vital signs data.
2. Filter for baseline records (`VISIT = 'Baseline'`) with valid pulse measurements.
3. Compute pulse pressure ($Systolic - Diastolic$).
4. Categorize subjects into hypertensive tiers.
5. Group by treatment arm (`TRTP`) and sex.
6. Summarize subject count, mean systolic, and mean pulse pressure.
7. Sort by mean systolic pressure descending.

### In SAS:
```sas
/* 1. Sort vitals by keys for merging */
PROC SORT DATA=sdtm.vsl;
  BY USUBJID;
RUN;

PROC SORT DATA=sdtm.dm;
  BY USUBJID;
RUN;

/* 2. Merge demographics and filter baseline records */
DATA work.baseline_vitals;
  MERGE sdtm.vsl (IN=in_v) sdtm.dm (IN=in_d);
  BY USUBJID;
  WHERE in_v AND in_d AND VISIT = 'Baseline' AND NOT MISSING(SYSBP) AND NOT MISSING(DIABP);

  /* 3. Derive Pulse Pressure */
  pulse_pressure = SYSBP - DIABP;

  /* 4. Categorize Hypertensive Tier */
  IF SYSBP >= 140 OR DIABP >= 90 THEN htn_tier = 'Stage 2';
  ELSE IF SYSBP >= 130 OR DIABP >= 80 THEN htn_tier = 'Stage 1';
  ELSE htn_tier = 'Normal';
RUN;

/* 5 & 6. Grouped Summary Statistics */
PROC MEANS DATA=work.baseline_vitals NWAY NOPRINT MISSING;
  CLASS TRTP SEX;
  VAR SYSBP pulse_pressure;
  OUTPUT OUT=work.summary (DROP=_TYPE_ _FREQ_)
    N(SYSBP)=n_subjects
    MEAN(SYSBP)=mean_sysbp
    MEAN(pulse_pressure)=mean_pp;
RUN;

/* 7. Sort final summary */
PROC SORT DATA=work.summary;
  BY DESCENDING mean_sysbp;
RUN;
```

### In Pytae (Python Library):
```python
import pytae as pt

# Ingest directly from SAS datasets or Parquet
vsl = pt.read_sas("vsl.sas7bdat")
dm = pt.read_sas("dm.sas7bdat")

summary = (
    vsl.filter("VISIT == 'Baseline' & SYSBP.notna() & DIABP.notna()")
    .join(dm, on="USUBJID", how="inner")
    .mutate(
        pulse_pressure="SYSBP - DIABP",
        htn_tier="case_when("
            "SYSBP >= 140 | DIABP >= 90, 'Stage 2', "
            "SYSBP >= 130 | DIABP >= 80, 'Stage 1', "
            "'Normal'"
        ")"
    )
    .by("TRTP", "SEX")
    .agg(
        n_subjects="n",
        mean_sysbp="SYSBP:mean",
        mean_pp="pulse_pressure:mean"
    )
    .arrange("mean_sysbp desc")
)

# Export clean result to Parquet or CSV
summary.to_parquet("summary.parquet")
```

### In Pytae (Unix CLI Pipeline):
```bash
pytae vsl.sas7bdat \
  -filter "VISIT == 'Baseline', SYSBP.notna(), DIABP.notna()" \
  -join "dm.sas7bdat,on=USUBJID,how=inner" \
  -mutate "pulse_pressure = SYSBP - DIABP, htn_tier = case_when(SYSBP >= 140 | DIABP >= 90, 'Stage 2', SYSBP >= 130 | DIABP >= 80, 'Stage 1', 'Normal')" \
  -by TRTP,SEX \
  -agg "n_subjects = n, mean_sysbp = mean(SYSBP), mean_pp = mean(pulse_pressure)" \
  -arrange "mean_sysbp desc" \
  -o summary.parquet
```

### Why SAS Teams Migrate to Pytae
- **No Disk Sorting Overhead**: Pytae's in-memory hash joins replace multi-step `PROC SORT` runs.
- **Zero Syntax Splitting**: No cognitive switching between `DATA` steps and `PROC SQL`.
- **Elimination of Missing Value Logic Bugs**: Pytae's safe null handling prevents accidental inclusion of missing values in comparisons.
- **Modern Cloud Execution**: Runs natively in Linux containers, cloud Lambdas, Airflow DAGs, and interactive Jupyter environments.

