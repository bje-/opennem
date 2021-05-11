from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import Response

from opennem.api.exceptions import OpennemBaseHttpException
from opennem.core.dispatch_type import DispatchType
from opennem.db import get_database_session
from opennem.db.models.opennem import Facility, FuelTech, Location, Network, Station
from opennem.schema.opennem import StationOutputSchema

from .schema import StationResponse

router = APIRouter()


class NetworkNotFound(OpennemBaseHttpException):
    detail = "Network not found"


class StationNotFound(OpennemBaseHttpException):
    detail = "Station not found"


class StationNoFacilities(OpennemBaseHttpException):
    detail = "Station has no facilities"


@router.get(
    "/",
    response_model=StationResponse,
    description="Get a list of all stations",
    response_model_exclude_none=True,
)
def stations(
    response: Response,
    session: Session = Depends(get_database_session),
    facilities_include: Optional[bool] = Query(True, description="Include facilities in records"),
    only_approved: Optional[bool] = Query(
        False, description="Only show approved stations not those pending"
    ),
    name: Optional[str] = None,
    limit: Optional[int] = None,
    page: int = 1,
) -> StationResponse:
    stations = session.query(Station).join(Location).enable_eagerloads(True)

    if facilities_include:
        stations = stations.outerjoin(Facility, Facility.station_id == Station.id).outerjoin(
            FuelTech, Facility.fueltech_id == FuelTech.code
        )

    if only_approved:
        stations = stations.filter(Station.approved == True)  # noqa: E712

    if name:
        stations = stations.filter(Station.name.like("%{}%".format(name)))

    stations = stations.order_by(
        # Facility.network_region,
        Station.name,
        # Facility.network_code,
        # Facility.code,
    )

    stations = stations.all()

    resp = StationResponse(data=stations, total_records=len(stations))

    response.headers["X-Total-Count"] = str(len(stations))

    return resp


@router.get(
    "/{country_code}/{network_id}/{station_code:path}",
    response_model=StationOutputSchema,
    description="Get a single station by code",
    response_model_exclude_none=True,
    # response_model_exclude={"location": {"lat", "lng"}},
)
def station(
    country_code: str,
    network_id: str,
    station_code: str,
    session: Session = Depends(get_database_session),
    only_generators: bool = Query(True, description="Show only generators"),
) -> StationOutputSchema:

    station = (
        session.query(Station)
        .filter(Station.code == station_code)
        .filter(Facility.station_id == Station.id)
        .filter(~Facility.code.endswith("NL1"))
        .filter(Facility.network_id == network_id)
        .filter(Network.country == country_code)
    )

    if only_generators:
        station = station.filter(Facility.dispatch_type == DispatchType.GENERATOR)

    station = station.one_or_none()

    if not station:
        raise StationNotFound()

    if not station.facilities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station has no facilities",
        )

    station.network = station.facilities[0].network_id

    return station
