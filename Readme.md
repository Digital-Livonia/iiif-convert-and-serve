# IIIF Conversion and Image API End-point

This docker image provides a RESTful image service that contains both an API for image transcoding as well as a full IIIF v3 Image API end-point.

Image transcoding can be performed using a HTTP `PUT` method request. Images are transcoded to tiled multi-resolution pyramid TIFF using the encoding parameters supplied as URL query parameters or the default parameters if no user-specified encoding parameters have been set.

Once transcoded, a JSON response will be sent which includes information on the transcoding time, transcoded image size, compression used, etc.

The optimized tiled pyramid TIFF images are then available through an instance of `iipsrv`, the IIPImage server, through `GET` (or `POST`) requests using standard IIIF v3 syntax.
Note that the image name that should be provided is that of the original source image provided during transcoding.

The transcoded TIFF images can be deleted using a HTTP `DELETE` request.
Note that this does **not** delete the original source image, but only the transcoded TIFF created by a HTTP `PUT` transcode command.

Source images can be stored within a folder shared between the host and the Docker instance or remotely within an instance of S3. In this case, the necessary S3 credentials should be provided (see **Startup Parameters** section below).

Note that the transcoded tiled multi-resolution pyramid TIFFs are stored locally and **not** in S3.

---

## Building the Docker Image

```bash
docker image build -t iiif:edge ./
```

---

## Authentication

Transcoding and deletion can be secured through the use of authentication tokens, which can be specified during docker image start-up.

To use authentication, the token must be added as a HTTP header:

```
Authorization: Bearer <token>
```

Example:

```
Authorization: Bearer ABCDEFGH
```

---

## Startup Parameters

A directory containing the source images must be supplied to the Docker container if not using S3.

Optionally, a directory for the transcoded TIFF images can also be provided. If no output directory is given, TIFF images are created and stored internally inside the Docker image.

### Encoding-related parameters

- **COMPRESSION**: jpeg, webp, deflate, zstd, none (default: webp)
- **TILESIZE**: tile size in pixels (default: 256)
- **QUALITY**: compression level (default: 50)
- **TOKEN** (optional): authentication token

### S3-related parameters

- **S3_HOST**
- **S3_ID**
- **S3_SECRET**
- **S3_BUCKET**

---

## Starting the Docker Image

```bash
docker run -it -p 8080:80   --mount type=bind,src=/home/user/images/,dst=/images/,ro   --rm iiif:edge
```

---

## Examples

```bash
curl -X PUT --header "Authorization: Bearer ABCDEFGH" http://localhost/image.jpg
```

```bash
curl http://localhost/image.jpg/full/500,/0/default.webp
```

---

## Funding

This work was supported by the Estonian Research Council under grant **PRG1276**:
Digital Livonia: For a Digitally Enhanced Study of Medieval Livonia (c. 1200–1550)
