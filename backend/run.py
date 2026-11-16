import asyncio
import sys

import uvicorn


def selector_loop_factory(*, use_subprocess: bool = False) -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        loop="run:selector_loop_factory",
    )
