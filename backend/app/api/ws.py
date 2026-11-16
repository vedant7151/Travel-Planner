from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.agents.graph import run_planning_graph
from app.core.auth import reset_request_user, set_request_user, verify_access_token
from app.core.logging import logger
from app.db.events import log_error, log_event

router = APIRouter()


@router.websocket("/plan/{trip_id}")
async def plan_ws(websocket: WebSocket, trip_id: str):
    authorization = websocket.headers.get("authorization", "")
    token = (
        authorization.removeprefix("Bearer ").strip()
        if authorization.lower().startswith("bearer ")
        else websocket.query_params.get("access_token")
    )
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        current_user = verify_access_token(token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    request_user_token = set_request_user(current_user)
    try:
        await websocket.accept()
        logger.info("websocket authenticated for user %s", current_user.id)
        await log_event(trip_id, "websocket_connected")
        try:
            async for update in run_planning_graph(trip_id):
                await websocket.send_json(update)
                if update.get("event") in {"done", "error"} and update.get("event") != "node":
                    break
        except WebSocketDisconnect:
            logger.info("websocket disconnected", extra={"trip_id": trip_id})
            await log_event(trip_id, "websocket_disconnected")
        except Exception as exc:
            logger.exception("websocket error: %s", exc)
            await log_error(trip_id, str(exc), agent="websocket")
            try:
                await websocket.send_json({"event": "error", "message": str(exc)})
            except Exception:
                pass
        await log_event(trip_id, "websocket_closed")
        await websocket.close()
    except Exception:
        pass
    finally:
        reset_request_user(request_user_token)
