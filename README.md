# Bank branch simulation

**How many ATMs, tellers and business tellers does a bank branch need, and what happens when it has too few?**

An **AnyLogic discrete-event simulation** of a bank branch, used to size its resources for five
demand scenarios: the class baseline, business customers, a different customer split, ATM-to-teller
rework and fluctuating arrivals. 24 runs, checked against queueing theory.

**AnyLogic · Python · Educational course project** | Author: Taim Salimoun

## The model and its results at a glance

![Schematic of the AnyLogic model: customers are split between an ATM, ordinary tellers and business tellers, with rework from the ATM back to the teller queue](docs/figures/flowchart.png)

Customers arrive, are routed to an ATM, a teller or a business teller, queue, are served and
leave. After the ATM, a share of customers must also see a teller (rework). Teller and business-teller
services seize staff from resource pools; the ATM is a Delay block whose capacity is the number of machines.

![Mean time in the bank for the chosen configuration of each task](docs/figures/chosen-configurations.png)

## The question and the approach

A branch needs enough staff to keep queues bounded without leaving them idle. Rather than guess,
each branch's **offered load** (arrival rate x routing share x mean service time) is computed first
to find the number of servers needed just to avoid saturation. The model is then run for each
configuration, with the buffer sizes given in the assignment and again with the buffers raised to
5,000, so that a configuration's failure shows up both as an event and as a magnitude.

## Key results

| Task | Demand scenario | Chosen resources (ATM / teller / business) | Time in the bank |
|---|---|---|---:|
| 1a | 2 customers/min, split 50/50 | 3 / 8 / – | 6.2 min |
| 2 | business customers, split 50/30/20 | 3 / 5 / 7 | 8.0 min |
| 3 | split 50/35/15 | 3 / 6 / 6 | 7.3 min |
| 4 | 25% of ATM users also need a teller | 3 / 8 / 6 | 8.3 min |
| 5 | fluctuating arrivals, about 6.2 customers/min | 7 / 22 / 14 | 8.4 min |

- **The class setup fails at once:** 1 ATM and 4 tellers halt the branch after 38.6 minutes, before
  40 customers are served. The offered-load calculation predicts it without any simulation.
- **Too few business tellers stops the bank:** 3 of them, against a need of 5.33, halt the run at
  101 minutes. With the buffer increased to 5,000, the business queue grows to 1,773 customers and the longest
  journey to about six days. Seven fix it.
- **A fourth ATM reduces waiting:** in Task 4 mean ATM waiting falls from 0.42 to 0.09 minutes,
  while the total visit falls from 8.34 to 8.03 minutes (3.8%) in this single-seed comparison.
  Whether that improvement justifies another ATM depends on service targets and costs.
- **Fluctuating arrivals are slower than they look:** `exponential(triangular(2.5, 5.5, 12.5))`
  produces 6.18 customers/min, not the 6.83 mean of the triangular distribution (Jensen's
  inequality). Using 6.83 would overestimate offered load by about 10.6%; integer staffing choices need separate evaluation.

![Share of the target run time each configuration completes with the specified buffers](docs/figures/survival-by-configuration.png)

Each configuration is a **single replication at a fixed seed**: exactly reproducible, but with no
confidence interval.

## Does the model do what it should?

![Measured versus predicted utilisation for all branches of all 24 runs](docs/figures/utilisation-validation.png)

Measured utilisation agrees with the offered-load prediction to within **1.6 percentage points**
for every stable run of 5,000+ minutes (**0.9** for the chosen configurations). Two runs with analytically stable loads stop early and differ by more than 1.7 points.
The 6.181/min Task 5 prediction is calculated independently from the arrival distribution.
A long single run is a diagnostic; it does not prove steady state. Full method, tables of assumptions and limits, including a note on how
two reasonable sizing rules give different Task 4 answers, are in
[docs/method-and-findings.md](docs/method-and-findings.md).

## Check the numbers yourself

Use **Python 3.12**, from the repository root:

```bash
python -m venv .venv
# Activate .venv for your operating system, then:
python -m pip install -r requirements.txt
python -m pytest tests -q
python scripts/analyze_runs.py --figures
```

[`data/bank-runs.csv`](data/bank-runs.csv) holds one row per recorded AnyLogic run (utilisation,
queue lengths, waiting and time in system, throughput). The script recomputes the validation and
redraws the three charts from it; the flowchart is an explanatory schematic, the tests assert the findings above.

**The `.alp` model files are not included.** They were built from a starter model supplied for a
university course, so only my own results, figures, scripts and write-up are published here.

## Repository map

| Path | Purpose |
|---|---|
| `docs/method-and-findings.md` | Model, sizing method, findings, verification and limits |
| `docs/figures/` | Model flowchart and charts generated from the data |
| `data/` | The 24 recorded runs and the original results table |
| `scripts/`, `tests/` | Validation, figures and checks (run in CI) |

## Scope, authorship and limits

**Author: Taim Salimoun.** I built the model in AnyLogic Personal Learning Edition, working from
AI-generated build guides; AI agents also helped write the analysis scripts and documentation. This
is an educational course project, not a study of a real bank.

Service times, arrival rates and splits are those given in the assignment. Results are single
replications, there are no costs, and "right-sized" means utilisation in a chosen band with short
queues, not minimum cost.

Original code and documentation are available under the [MIT license](LICENSE). Course-material and
software notices are in [NOTICE.md](NOTICE.md).
