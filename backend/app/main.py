from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from app.config import security_settings
from app.routers import application, reminder, user

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[security_settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(application.router)
app.include_router(reminder.router)
app.include_router(user.router)


@app.get("/scalar", include_in_schema=False)
def get_scalar_docs():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title="Scalar Api")
