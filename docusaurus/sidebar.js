const sidebars = {
    defaultSideBar: [
        "introduction",
        {
            type: 'category',
            label: 'Getting Started',
            items: [
                {
                    type: 'doc',
                    id: 'Getting Started/installation',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/example-application',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/application-setup',
                },
                {
                  type: 'doc',
                  id: 'Getting Started/strategies',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/credentials',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/portfolio-configuration',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/orders',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/positions',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/trades',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/tasks',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/metrics',
                },
            ],
        },
        {
            type: 'category',
            label: 'Risk Rules',
            items: [
                {
                    type: 'doc',
                    id: 'Risk Rules/overview',
                },
                {
                    type: 'doc',
                    id: 'Risk Rules/position-size',
                },
                {
                    type: 'doc',
                    id: 'Risk Rules/stop-loss-rule',
                },
                {
                    type: 'doc',
                    id: 'Risk Rules/take-profit-rule',
                },
                {
                    type: 'doc',
                    id: 'Risk Rules/scaling-rule',
                },
                {
                    type: 'doc',
                    id: 'Risk Rules/exposure-rule',
                },
                {
                    type: 'doc',
                    id: 'Risk Rules/cooldown-rule',
                },
                {
                    type: 'doc',
                    id: 'Risk Rules/trading-cost',
                },
            ],
        },
        {
            type: 'category',
            label: 'Data',
            items: [
                {
                    type: 'doc',
                    id: 'Data/download',
                },
                {
                    type: 'doc',
                    id: 'Data/market-data-sources',
                },
                {
                    type: 'doc',
                    id: 'Data/multiple-market-data-sources',
                },
                {
                    type: 'doc',
                    id: 'Data/external-data',
                },
            ],
        },
        {
            type: 'category',
            label: 'Advanced Concepts',
            items: [
                {
                    type: 'doc',
                    id: 'Advanced Concepts/backtest-optimization',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/blotter',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/fx-conversion',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/custom-data-providers',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/logging-configuration',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/execution-logic',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/recording-variables',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/portfolio-sync',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/position-modes',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/confluence-cards',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/permutation-testing',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/mcp-server',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/mirror-stop-loss-take-profit',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/pipelines',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/pipelines-live',
                },
            ],
        },
        {
            type: 'category',
            label: 'Backtesting',
            items: [
                {
                    type: 'doc',
                    id: 'Getting Started/backtesting',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/studies',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/universes',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/backtest-windows',
                },
                {
                    type: 'category',
                    label: 'Engines',
                    items: [
                        {
                            type: 'doc',
                            id: 'Getting Started/event-backtesting',
                            label: 'Event-Driven Backtesting',
                        },
                        {
                            type: 'doc',
                            id: 'Getting Started/vector-backtesting',
                            label: 'Vector Backtesting',
                        },
                        {
                            type: 'doc',
                            id: 'Advanced Concepts/vector-backtesting',
                            label: 'Scaling Backtests',
                        },
                    ],
                },
                {
                    type: 'category',
                    label: 'Results and Data',
                    items: [
                        {
                            type: 'doc',
                            id: 'Getting Started/open-backtest-format',
                        },
                        {
                            type: 'doc',
                            id: 'Getting Started/backtest-reports',
                        },
                        {
                            type: 'doc',
                            id: 'Getting Started/backtest-storage',
                        },
                        {
                            type: 'doc',
                            id: 'Data/backtest_data',
                            label: 'Inspecting Backtest Data',
                        },
                    ],
                },
                {
                    type: 'category',
                    label: 'Pipeline Integration',
                    items: [
                        {
                            type: 'doc',
                            id: 'Advanced Concepts/pipelines-event-backtest',
                            label: 'Event-Driven Pipelines',
                        },
                        {
                            type: 'doc',
                            id: 'Advanced Concepts/pipelines-vector-backtest',
                            label: 'Vector Pipelines',
                        },
                    ],
                },
            ],
        },
        {
            type: 'category',
            label: 'Going Live',
            items: [
                {
                    type: 'doc',
                    id: 'Getting Started/deployment',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/paper-trading',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/deployment-aws-lambda',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/deployment-azure-functions',
                },
            ],
        },
        {
            type: "category",
            label: "Contributing Guide",

            items: [
                {
                    type: 'doc',
                    id: 'Contributing Guide/contributing',
                },
                {
                    type: 'doc',
                    id: 'Contributing Guide/style-guide',
                },
            ],
        },
    ],
};

module.exports = sidebars;
