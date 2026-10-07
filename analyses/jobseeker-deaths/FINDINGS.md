# JobSeeker deaths: findings log

Session of 7 October 2026. Review of Greg Jericho's Grogonomics column ([Guardian, 17 September 2026](https://www.theguardian.com/business/grogonomics/2026/sep/17/australians-jobseeker-dying-in-poverty)) against the AIHW report it cites.

- Draft post: `C:\dev\inthegame-blog\blog\2026-10-07-jobseeker-deaths\index.qmd` (`dev`, `draft: true`). Stats, tables, bullets and charts only; Pete writes the prose.
- Idea entry: [[ideas]] under Blog posts.
- Data in this folder: `aihw-phe-354-income-support-mortality.xlsx` (AIHW workbook), `jobseeker_capacity_mortality.csv` (DSS partial-capacity series joined to AIHW death rates).

## Verdict

- **Agree:** the gap is real and large. JobSeeker recipients die at about 4.9x the non-welfare rate (326 vs 67 per 100,000, age-standardised, 2022); 9.6x at ages 35-44. Every number in the article reproduces from the AIHW workbook.
- **Disagree:** the lives-saved figures (1,246 and 3,168). AIHW says the report gives no causal evidence. The 2020 baseline is a change in who was on the payment (AIHW's own reading). "Same rate as non-welfare" assumes nobody arrives already sick.
- **Missed driver:** who is on the payment. Partial capacity to work rose from 27% to 43% of recipients (2014-2019) as the DSP shrank; the death rate rose 44% in step while the payment's real value was flat.
- **Smaller issue:** double counting, at most 18% of 2022 JobSeeker deaths.
- **Twist:** the policy lever may be DSP access as much as the JobSeeker rate.
- **Counterweight:** deaths of despair fell further than composition predicts from 2020 (see below). Suggestive, 3 years.
- **Also:** only about half of AIHW's "JobSeeker deaths" were on JobSeeker at death (DSS FOI 2122-068).

## Source: AIHW PHE 354

- [Report](https://www.aihw.gov.au/reports/centrelink/mortality-outcomes-people-receiving-income-support), September 2026. ABS PLIDA linked data, ages 22-64, 2012-2022. [Workbook](https://www.aihw.gov.au/getmedia/e5b362ea-7a22-4677-a72c-d70b083bb571/aihw-phe-354-income-support-mortality.xlsx), Tables S1-S14.
- Counting: a person is in every payment group they were paid from in their year of death. Denominator = anyone paid at any point in the year.
- Jericho's 328 / 224 / 300 / 326 (2019-2022) are the age-standardised unemployment-payment rates (Table S3.2). His 1,246 = 3,985 x (1 - 224/326); his 817 = 3,985 x 66.8/326.
- 2020: deaths rose 3,539 to 4,483; recipients about 1.04m to 2.05m. AIHW: drop "likely due to the large numbers of additional unemployment payment recipients".

## Death rates by group, 2022

Deaths per 100,000 a year, age-standardised (crude in brackets). Lower is better.

| Group | Rate | Deaths | x non-welfare |
|---|---|---|---|
| Not on a working-age payment | 67 (66) | 11,259 | 1.0 |
| All income support | 541 (626) | 14,744 | 8.1 |
| JobSeeker | 326 (340) | 3,985 | 4.9 |
| DSP | 1,174 (1,637) | 10,622 | 17.6 |
| Carer | 169 (232) | 646 | 2.5 |
| Parenting | 95 (56) | 197 | 1.4 |

## Double counting

Sum of the four payment-group deaths minus all-recipient deaths = deaths counted in 2+ groups. Upper bound on double-counted JobSeeker deaths.

| Year | JobSeeker deaths | In 2+ groups | Max share |
|---|---|---|---|
| 2012 | 2,040 | 521 | 26% |
| 2019 | 3,539 | 667 | 19% |
| 2020 | 4,483 | 589 | 13% |
| 2021 | 4,894 | 866 | 18% |
| 2022 | 3,985 | 706 | 18% |

Dropping all 706 in 2022 leaves the rate at no lower than about 268, still 4x non-welfare.

### On JobSeeker at death vs "paid at some point that year"

DSS FOI 2122-068 ([document](https://dss.gov.au/system/files/foi-attachments/foi-2122-068-document.pdf), ref ADH22-0025, created under s17, released 14 February 2022): Newstart/JobSeeker payments cancelled because the recipient died. All ages; excludes people not on payment at death and people whose payment was cancelled for another reason after death.

| Year | Cancelled due to death (DSS) | AIHW "unemployment payment" deaths (22-64) | On JobSeeker at death |
|---|---|---|---|
| 2019 | 1,903 | 3,539 | 54% |
| 2020 | 2,567 | 4,483 | 57% |
| 2021 | 2,223 | 4,894 | 45% |

- Roughly half the deaths AIHW counts as "JobSeeker deaths" were people not on JobSeeker when they died, or whose payment was ended for a non-death reason (for example, stopping reporting).
- The two can't be separated from public data. The 18% double-count bound only covers people who moved to another working-age payment; people who moved off payments entirely are invisible in it.
- DSS has already produced this exact extract under s17, so an FOI asking for the same table plus a partial-capacity column is a small extension.

## Partial capacity to work

- Definition: [SS Guide 1.1.P.65](https://guides.dss.gov.au/social-security-guide/1/1/p/65), SSAct s16B. Impairment prevents 30+ hours a week at minimum wage within 2 years, "regardless of whether the condition/s ... are reasonably treated and stabilised". DSP needs inability to work 15+ hours and a stabilised condition (AIHW glossary). People in between stay on JobSeeker.
- Source: DSS Benefit and Payment Recipient Demographics, quarterly ([data.gov.au](https://data.gov.au/data/dataset/dss-payment-demographic-data)), sheet "Partial Capacity to Work". First published June 2014.
- **Definition change, June 2019:** previously only recipients assessed in the last 2 years; now anyone with an under-30-hours capacity on record. DSS published a revised back-series to June 2014 in the June 2019 file; 2014-2018 here use it. Old basis Dec 2018: 199,907; revised: 284,924. Reason for the change not stated.
- By age: published from December 2021 ("Work Capacity selected payments" sheet).

Share with partial capacity (December) and death rate (age-standardised, per 100,000):

| Year | Share | Death rate |
|---|---|---|
| 2014 | 26.8% | 228 |
| 2015 | 29.0% | 238 |
| 2016 | 31.9% | 264 |
| 2017 | 35.3% | 296 |
| 2018 | 39.4% | 307 |
| 2019 | 42.8% | 328 |
| 2020 | 29.1% | 224 |
| 2021 | 40.0% | 300 |
| 2022 | 42.8% | 326 |

- Correlation 0.976 (n = 9). Line fitted on 2014-19 predicts 2020-22 at 244 / 314 / 332 vs actual 224 / 300 / 326.
- The 2020 test is not independent: the lockdown influx lowered both series. Lagged one year, correlation 0.19 (2015-22); pre-2020 lagged 0.97 (shared trend).
- Not leakage: about 360,000 partial-capacity recipients vs about 4,000 deaths a year.
- DSP Dec 2014 824,470 to Dec 2018 750,045 (-74,000, all ages); partial capacity +117,000 to 2019. DSP shrinkage covers at most about 60% of the rise.

### Partial capacity back to 2007

Newstart recipients with an assessed partial capacity to work, June each year (Services Australia, ADH19-0469, released under DSS FOI 19/20-073, document 2; extracted and checked against the page 7 October 2026).

| 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2016 | 2019 |
|---|---|---|---|---|---|---|---|---|---|
| 30,417 | 54,339 | 74,427 | 91,178 | 98,707 | 116,174 | 150,727 | 180,646 | 230,444 | 289,489 |

- Extends the public DSS series (from June 2014) back to 2007. 2014-2019 values match DSS's revised back-series exactly, so it's the same definition.
- Nearly flat 2010-2011 (+8%), then +18% (2012) and +30% (2013): the jump lands right after the DSP program of support (September 2011) and new impairment tables (January 2012).
- Shares need Newstart totals for 2007-2013 (not yet sourced); counts alone don't control for the number of unemployed (the GFC raised it 2008-09).
- Source: [DSS FOI 19/20-073](https://www.dss.gov.au/system/files/foi-attachments/foi-request-1920-073-documents.pdf) disclosure log (document archived locally in foicommons).

### DSP grant rate (checked 7 October 2026)

[ACOSS submission to the 2021 Senate DSP inquiry](https://www.acoss.org.au/wp-content/uploads/2021/09/ACOSS-DSP-INQUIRY-FINAL.pdf), figure 2, citing DSS and Services Australia data. Share of DSP claims granted:

| 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 |
|---|---|---|---|---|---|---|---|---|---|---|
| 63.9% | 59.8% | 48.5% | 43.3% | 40.7% | 36.9% | 25.7% | 27.8% | 29.8% | 37.3% | 41.3% |

- Confirms the DSP tightening behind the partial-capacity rise. The grant rate bottomed in 2016; the partial-capacity share kept climbing to 2019 because the stuck group accumulates.
- ACOSS also says almost half of pre-pandemic JobSeeker recipients couldn't work full time because of incapacity, consistent with the DSS series (42.8% in December 2019).
- Raw Senate Estimates answers (e.g. DSS 2014-15 supplementary, QoN 542) exist but returned 403; not read.

## Estimated death rates: full vs partial capacity

Straight line: rate = full x (1 - share) + partial x share, fitted through the nine years. Assumes each group's own rate is constant over time.

| Version | Full capacity | Partial capacity |
|---|---|---|
| Age-standardised, all 9 years | 52 (95% CI 6 to 98) | 696 (± 83) |
| Age-standardised, without 2020 | 68 (26 to 109) | 673 (± 73) |
| Crude, all 9 years (ignore) | 15 (-37 to 68) | 773 (± 96) |

- Full capacity at about the non-welfare rate; partial capacity about 10x non-welfare and 60% of the DSP rate.
- Methods that gave impossible answers: yearly death counts (full = 2), 2019 vs 2020 solve (full = -40), 2021-22 age bands (negative both ways). The share rises with age, as do death rates, so totals can't separate them.
- Measured split exists only in person-level records: FOI to Services Australia (Pete lodges; Claude drafts), or an AIHW data request.

## Deaths of despair: the strongest evidence for Jericho's side

AIHW Table S13 (unemployment payments) and S12 (non-recipients): suicide + accidental poisoning + alcoholic liver disease, crude per 100,000, 22-64.

| Year | JobSeeker despair rate | Predicted from share (fit 2014-19) | Gap | All-cause gap | Non-recipient despair rate |
|---|---|---|---|---|---|
| 2014 | 75.1 | | | | 10.5 |
| 2019 | 116.4 | | | | 12.0 |
| 2020 | 73.1 | 84 | -12% | -9% | 11.3 |
| 2021 | 90.7 | 111 | -18% | -6% | 10.5 |
| 2022 | 98.0 | 118 | -17% | -2% | 11.3 |

- About a third of JobSeeker deaths; rose 55% 2014-2019. Correlation with the partial-capacity share 0.82 (all-cause 0.98).
- Post-2020 these fell further below the composition prediction than all causes, and stayed down. Non-recipients fell too (-6% / -12% / -6% vs 2019), so JobSeeker's extra drop is roughly 6-11%.
- Candidate causes: Coronavirus Supplement, 1 April 2021 permanent $50 rise, paused mutual obligations (dates in the policy timeline). n = 3 years, 2022 data preliminary: suggestive, unresolved.

## Policy timeline (checked 7 October 2026)

| Date | Change | Source |
|---|---|---|
| 3 September 2011 | DSP: unless 20+ points on a single impairment table, claimants must first do 18 months in a "program of support" | [Senate Community Affairs report](https://aph.gov.au/Parliamentary_Business/Committees/Senate/Community_Affairs/Completed_inquiries/2010-13/familyassistance11/report/c04); [Legal Aid NSW](https://www.legalaid.nsw.gov.au/ways-to-get-help/publications-and-resources/disability-support-pension) |
| 1 January 2012 | DSP: revised impairment tables (first full review since 1993) | [Minister Macklin media release](https://formerministers.dss.gov.au/13610/updated-impairment-tables-for-disability-support-pensioners) |
| March 2020 | Mutual obligations suspended (resumed in phases from 9 June 2020, no penalties at first) | [InDaily, 3 June 2020](https://indaily.com.au/news/2020/06/03/centrelink-mutual-obligations-to-resume-for-unemployed-but-questions-remain) |
| 27 April 2020 | Coronavirus Supplement $550 a fortnight | [Thomson Reuters](https://insight.thomsonreuters.com.au/tax/posts/jobseeker-supplement-extended-to-march-2021-at-reduced-rate) |
| 25 September 2020 | Supplement cut to $250 | same |
| 1 January 2021 | Supplement cut to $150 | same |
| 31 March 2021 | Supplement ends | same |
| 1 April 2021 | Permanent JobSeeker rise of $50 a fortnight; income-free area to $150 | [Minister Ruston media release](https://formerministers.dss.gov.au/?p=19375); [Bills Digest 55, 2020-21](https://aph.gov.au/Parliamentary_Business/Bills_Legislation/bd/bd2021a/21bd055) |

- The DSP grant rate fell from 59.8% (2011) to 48.5% (2012) and 25.7% (2016), in line with the 2011-12 rule changes.
- The 2021-22 despair-death drop sits after the permanent rise, so a payment effect can't be ruled out for those years.
- The 27 April 2020 start date is from the payment's design (well known) but the source above confirms only the later steps; check before quoting.

## Open items

- [ ] FOI request to DSS: drafted in [[foi-request-draft]] (7 October 2026); Pete lodges.
- [x] Check DSP rule-change dates: program of support 3 September 2011, impairment tables 1 January 2012 (7 October 2026).
- [ ] Rebuild the flow chart as an interactive SVG (site rule); current mermaid version is a placeholder.
- [ ] Check light mode and real-mouse hover on the draft.
