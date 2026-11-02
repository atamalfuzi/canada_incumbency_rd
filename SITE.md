# Text for the website

Proposed text for the portfolio. The site's own session decides where it goes. Figures are in [figures/](figures/), and numbers come from [output/](output/).

## Portfolio entry

**Incumbency in the Canadian Parliament**

Regression discontinuity replication and extension, 2022 and 2026

A party that narrowly wins a federal riding is about 12 points more likely to win it next time, across elections from 1872 to 2025. I reproduced my 2022 replication of Kendall and Rekkas exactly, then added data-driven bandwidths, validity checks and five new elections, linking ridings across two redistributions by the voters they share. Since 2011 the data can't separate the estimate from earlier periods, and it depends on how the redistributions are handled.

Links: [repository](https://github.com/atamalfuzi/canada_incumbency_rd)

## Project page

### Does winning a riding help a party win it again?

Parties that win a riding tend to win it again, but mostly because they were strong there already. Comparing candidates who just won with those who just lost separates the advantage of winning from that strength. In 2022 I replicated Kendall and Rekkas's study of this for a course at SFU and wrote a critique of it. This project reruns that work in Python, applies current methods, tests the points the critique raised and adds the elections from 2011 to 2025.

Figure: `figures/rd_plot.png`

A narrow win adds 11.6 points to a party's chance of winning the riding next time (95% range 4.9 to 16.0), for Liberal and Conservative candidates from 1872 to 2025. All 20 estimates in the 2022 table reproduce, with their standard errors and sample sizes.

### Bandwidth

The critique asked whether the result depends on the two bandwidths the paper reports. It changes little between 5 and 15 points. Past 20 it climbs, because a straight line is being fitted through a curve, and the bias-corrected estimate stays near 0.11. The paper's cubic and quartic fits over ±70% are kept only for comparison, following Gelman and Imbens (2019).

Figure: `figures/bandwidth.png`

### Since 2008

Federal ridings were redrawn before the 2015 and 2025 elections, so most new ridings have no exact predecessor. I linked ridings by their shared voters, using Elections Canada's transposition for 2013 and rebuilding the flows from 2021 polling divisions for 2023. At 75% overlap, 217 of 338 ridings link in 2015 and 283 of 343 in 2025. The rebuilt 2023 flows match Elections Canada's transposed elector counts with a correlation of 0.999.

Figure: `figures/link_rules.png`

The estimate since 2011 is 15.6 points (−1.9 to 27.4), and it runs from 10 to 30 depending on the linking rule. I can't say that the advantage has changed.

Figure: `figures/eras.png`

### Other checks

Dividing the margin by eligible voters instead of votes cast, as the critique proposed, changes little: 12.7 points against 14.2 for 2006 to 2025. False cutoffs show no jumps, and a narrow win doesn't change whether a party runs again. Two checks are less clean: the density of Conservative margins before 1950, and narrow winners being somewhat less likely to have won two elections back.

Figure: `figures/placebo.png`

Working with the source file also showed that 159 of its 308 winning margins for 2008 are measured against the third-place candidate. This doesn't affect the 2022 numbers.

Personal project. This is my own analysis of publicly available data. It is not associated with my work for any current or past employer and does not represent their views.

Python, statsmodels, rdrobust, rddensity, geopandas. Data from Elections Canada; the 1867-2008 file is from Kendall and Rekkas and isn't redistributed. [Code and tables on GitHub](https://github.com/atamalfuzi/canada_incumbency_rd).

Figures to use, in order: `rd_plot.png`, `bandwidth.png`, `link_rules.png`, `eras.png`, `placebo.png`. `party_period.png` is optional.
