workspace "Hacker News Crawler" "C4 container view of the local application" {
    model {
        reader = person "Reader" "Browses and filters Hacker News stories"
        hn = softwareSystem "Hacker News" "Provides the public front-page HTML" {
            tags "External"
        }

        crawler = softwareSystem "Hacker News Crawler" "Shows the first 30 stories and records API usage" {
            web = container "Web application" "Renders the three story views and requests entries from the API" "Next.js"
            api = container "Entries API" "Scrapes and caches a 30-story snapshot, filters entries, and records usage" "FastAPI / Python"
            db = container "Usage database" "Persists API usage events" "PostgreSQL" {
                tags "Database"
            }
            migrate = container "Migration runner" "Applies database schema migrations at startup" "Alembic / Python"
        }

        reader -> web "Browses story views" "HTTP"
        web -> api "Requests filtered entries" "HTTP / JSON"
        api -> hn "Fetches front-page HTML on cache miss" "HTTPS"
        api -> db "Writes one usage event per valid request" "SQL"
        migrate -> db "Applies schema migrations" "SQL"
    }

    views {
        container crawler "Containers" {
            include *
            autoLayout lr
        }

        styles {
            element "Person" {
                shape Person
                background #08427b
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
            element "Database" {
                shape Cylinder
            }
            element "External" {
                background #999999
                color #ffffff
            }
        }
    }
}
