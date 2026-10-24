"""Stream complete large read responses across the hosted buffered-body limit."""

from fastapi.responses import JSONResponse, StreamingResponse

STREAM_THRESHOLD = 1024 * 1024


class CloudJSONResponse(JSONResponse):
    async def __call__(self, scope, receive, send):
        if len(self.body) <= STREAM_THRESHOLD:
            return await super().__call__(scope, receive, send)

        def chunks():
            for offset in range(0, len(self.body), 65536):
                yield self.body[offset : offset + 65536]

        response = StreamingResponse(
            chunks(), status_code=self.status_code, background=self.background
        )
        response.raw_headers = [
            (key, value) for key, value in self.raw_headers if key != b"content-length"
        ]
        return await response(scope, receive, send)


def streamed_download(path, filename):
    def chunks():
        with path.open("rb") as stream:
            while data := stream.read(65536):
                yield data

    return StreamingResponse(
        chunks(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="' + filename + '"'},
    )
