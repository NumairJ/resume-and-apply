from fastapi import FastAPI

from routers import applications, jobs, profile, providers, resumes


def create_app() -> FastAPI:
    app = FastAPI(title="Job Match Assistant")

    # Routers are mounted at their bare resource path. The Next.js rewrite strips the
    # /api prefix, so /api/profile in the browser arrives here as /profile.
    app.include_router(profile.router)
    app.include_router(jobs.router)
    app.include_router(providers.router)
    app.include_router(resumes.router)
    app.include_router(applications.router)

    # Liveness only — deliberately no database query. The db service has its own
    # healthcheck and the backend waits on it, so querying here would add a failure
    # mode without adding information.
    #
    # Path and body are load-bearing: the Dockerfile HEALTHCHECK hits "/", and the
    # frontend placeholder page renders this message through the /api rewrite.
    @app.get("/")
    def health() -> dict[str, str]:
        return {"message": "Backend is running"}

    return app


app = create_app()
