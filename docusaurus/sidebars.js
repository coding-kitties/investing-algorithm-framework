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
                    id: 'Getting Started/simple-example',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/application-setup',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/portfolio-configuration',
                },
                {
                  type: 'doc',
                  id: 'Getting Started/strategies',
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
                    id: 'Getting Started/backtesting',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/vector-backtesting',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/backtest-reports',
                },
                {
                    type: 'doc',
                    id: 'Getting Started/deployment',
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
                {
                    type: 'doc',
                    id: 'Data/backtest_data',
                },
            ],
        },
        {
            type: 'category',
            label: 'Advanced Concepts',
            items: [
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
                    id: 'Advanced Concepts/vector-backtesting',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/OPTIMIZATION_GUIDE',
                },
                {
                    type: 'doc',
                    id: 'Advanced Concepts/PARALLEL_PROCESSING_GUIDE',
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
