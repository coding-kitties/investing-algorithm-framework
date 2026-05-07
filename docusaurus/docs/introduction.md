---
sidebar_position: 1
slug: /
---

# Introduction

Welcome to the Investing Algorithm Framework documentation! This framework provides a comprehensive platform for creating, testing, and deploying algorithmic trading strategies.

## What is the Investing Algorithm Framework?

The Investing Algorithm Framework is a Python-based library designed to help developers and traders build sophisticated algorithmic trading systems. It provides:

- **Strategy Development**: Tools for creating and implementing trading strategies
- **Backtesting**: Comprehensive backtesting capabilities with both event-based and vector-based approaches
- **Data Management**: Integration with multiple data sources and providers
- **Order Management**: Advanced order execution and portfolio management
- **Performance Analysis**: Detailed analytics and metrics for strategy evaluation
- **Deployment**: Production-ready deployment capabilities

## Key Features

- 📊 **30+ Metrics** — CAGR, Sharpe, Sortino, Calmar, VaR, CVaR, Max DD, Recovery & more
- 🧮 [Cross-Sectional Pipelines](./Advanced%20Concepts/pipelines)** — Rank, filter and score entire universes of symbols every iteration with a tidy factor table
- ⚡ [Vector Backtesting for Signal Analysis](./Advanced%20Concepts/vector-backtesting)** — Quickly test your strategy logic on historical data to see how signals would have behaved before committing to full event-driven backtests
- 🏃 [Event-Driven Backtesting](./Advanced%20Concepts/event-driven-backtesting)** — Once promising strategies are identified via vector backtests, run full event-driven backtests to simulate realistic execution and portfolio management
- 🔀 [Permutation Testing / Monte Carlo Simulations](./Advanced%20Concepts/permutation-testing)** — Assess the statistical robustness of your strategies by running them across randomized market scenarios to see how often your results could occur by chance
- 🚀 [Deployment](./Getting%20Started/deployment) — Once the best strategy is identified through backtesting and comparison, deploy it to production locally or in the cloud (AWS Lambda / Azure Functions) to start live trading
- ⚔️ **Multi-Strategy Comparison** — Rank, filter & compare strategies in a single interactive report
- 🪟 **Multi-Window Robustness** — Test across different time periods with window coverage analysis
- 📈 **Equity & Drawdown Charts** — Overlay equity curves, rolling Sharpe, drawdown & return distributions
- 🗓️ **Monthly Heatmaps & Yearly Returns** — Calendar heatmap per strategy with return/growth toggles
- 🎯 **Return Scenario Projections** — Good, average, bad & very bad year projections from backtest data
- 📉 **Benchmark Comparison** — Beat-rate analysis vs Buy & Hold, DCA, risk-free & custom benchmarks
- 📄 [One-Click HTML Report](./Getting%20Started/backtest-reports) — Self-contained file, no server, dark & light theme, shareable
- 📦 **Custom `.iafbt` Backtest Bundle Format** — An explicit, versioned, compressed, language-portable container (zstd + msgpack with magic-byte header) plus a separate parquet index for fast filtering without loading. ~21× smaller and ~27× fewer files than standard filebased directory layouts, with parallel I/O for fast load/save of large amounts of backtests.
- 🌐 **Load External Data** — Fetch CSV, JSON, or Parquet from any URL with caching and auto-refresh
- 📝 **[Record Custom Variables](./Advanced%20Concepts/recording-variables)** — Track any indicator or metric during backtests with `context.record()`
- 🚀 **Build → Backtest → Deploy** — Local dev, cloud deploy (AWS / Azure), or monetize on Finterion

## Getting Started

Ready to start building your first trading algorithm? Head over to our [Installation Guide](Getting%20Started/installation) to get up and running in minutes!

## Community & Support

- **GitHub**: [investing-algorithm-framework](https://github.com/coding-kitties/investing-algorithm-framework)
- **Issues**: Report bugs or request features on GitHub Issues
- **Discussions**: Join the community discussions

---

Let's dive in and start building your algorithmic trading system!
