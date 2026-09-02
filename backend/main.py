from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Job Match Assistant")

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
