const sidebars = {
    defaultSideBar: [
        "introduction",
        "contributing",
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
            ],
        },
        {
            type: "contributing",
            label: "Contributing",
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
        {
            type: 'category',
            label: 'Advanced Concepts',
            items: [
                {
                    type: 'doc',
                    id: 'Advanced Concepts/logging-configuration',
                },
            ],
        },
    ],
};

module.exports = sidebars;
