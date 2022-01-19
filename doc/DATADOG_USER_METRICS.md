# Collecting user metrics from DataDog

### Requirements

- `DATADOG_API_KEY_ID` must be set in `setup-env`
- `DATADOG_API_KEY_ID` must represent a registered application in DataDog, and the must be an associated App key.
- The value of `DATADOG_API_KEY_ID` must be present in AWS Secrets Manager; currently, it is a manual step to set this up

### Currently available script(s) for collecting user metrics

[`get-datad-user-metrics`](https://github.com/spacetelescope/jupyterhub-deploy/blob/main/tools/get-datadog-user-metrics) is the only script developed so far, and is intended to produce a sanitized report of the number of unique users on a given Science Platform for a specified week, as well as how many hours each of those users spent on the Platform.  Usage and sample output looks like this:

```
$ get-datadog-user-metrics --end-date '2021-12-18'

User data for week ending on 2021-12-18
----------------------------------------

Number of unique users: 26

Total usage hours per user (anonymized):
	AuZYDr	120
	NtMrPn	61
	sgQtcQ	22
	oaQcxW	15
	eadXqU	7
	pQLyqA	6
	GIbNml	5
	zlNNOn	3
	hayfoT	3
	FaaGoa	3
	aPyxNw	2
	NHkDOz	2
	LLlPeb	2
	fYdGap	2
	ymyktu	2
	gOQbcY	2
	ALYIQu	2
	mjaqyL	2
	slfsYt	2
	flDHTw	2
	cbECCU	1
	HRRTze	1
	wHMkgb	1
	lQJiCf	1
	pfMiIg	1
	xzxifY	1
```
