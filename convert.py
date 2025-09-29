#!/usr/bin/python3

#
# Simple RESTful end-point for image conversion to tiled pyramid multi-resolution TIFF
#
# Enables image conversion and deletion of converted TIFF via PUT and DELETE HTTP verbs
# Accepts query parameters: compression, quality and tilesize to tune transcoding
# Optional authenication through token and "Authorization: Bearer" HTTP header
#
# Author: Ruven Pillay <ruven@users.sourceforge.net>
#
#

from flask import Flask, request, abort
from time import perf_counter
import pyvips
import os
import sys
import glob
import botocore
import boto3


app = Flask(__name__)



# Define these statically within Docker environment
PREFIX='/images/'
TIFF_PREFIX='/home/tiff/'


# Allow environment variables for configuration
app.config.from_prefixed_env()

if "PREFIX" in app.config:
    PREFIX = app.config["PREFIX"]

if "TIFF_PREFIX" in app.config:
    TIFF_PREFIX = app.config["TIFF_PREFIX"]


# Check whether output directory can be written to
if not os.access( TIFF_PREFIX, os.W_OK ):
    raise Exception( f'Output directory "{TIFF_PREFIX}" not writable' )



# Set up some parameters
token = None
if "TOKEN" in app.config:
    token = app.config["TOKEN"]

# Set default compression
COMPRESSION = 'webp'
if "COMPRESSION" in app.config:
    COMPRESSION = app.config["COMPRESSION"]

# Set default quality
QUALITY=50
if "QUALITY" in app.config:
    QUALITY = app.config["QUALITY"]

# Set tile size
TILESIZE = 256
if "TILESIZE" in app.config:
    TILESIZE = app.config["TILESIZE"]


# Print out our configuration
print( '-----------------------' )
print( 'Configuration:' )
print( f'TOKEN: {token}' )
print( f'COMPRESSION: {COMPRESSION}' )
print( f'QUALITY: {QUALITY}' )
print( f'TILESIZE: {TILESIZE}x{TILESIZE}' )
print( '-----------------------' )


# Connect to S3 if configured
s3 = None
bucket = None
if "S3_HOST" in app.config and "S3_ID" in app.config and "S3_SECRET" in app.config and "S3_BUCKET" in app.config:
    try:

        # First check whether input directory can be written to
        if not os.access( PREFIX, os.W_OK ):
            raise Exception( 'Input directory needs to be writable when using S3' )

        s3 = boto3.resource( "s3",
                             endpoint_url = app.config["S3_HOST"],
                             aws_access_key_id = app.config["S3_ID"],
                             aws_secret_access_key = app.config["S3_SECRET"],
                             aws_session_token = None )

        # Set bucket
        bucket = s3.Bucket( app.config["S3_BUCKET"] )

        # Check connection
        s3.meta.client.head_bucket( Bucket=bucket.name )
        print( f'Connected to S3 bucket "{app.config["S3_BUCKET"]}" on {app.config["S3_HOST"]}' )
        print( '-----------------------' )

    except botocore.exceptions.ClientError as e:
        s3 = None
        print( f'Unable to connect to S3 bucket "{app.config["S3_BUCKET"]}"' )

        # If a client error is thrown, distinguish between 404 and 403 errors
        error_code = int(e.response['Error']['Code'])
        if error_code == 403:
            print( "S3: Private Bucket: Access forbidden!" )
        elif error_code == 404:
            print( "S3: Bucket Does Not Exist!" )

    except Exception as e:
        s3 = None
        sys.exit( f'Unable to connect to S3 bucket "{app.config["S3_BUCKET"]}"' )




# Check input and output directories
if not os.access( PREFIX, os.R_OK ):
    sys.exit( f'Unable to read from input directory {PREFIX}' )
if not os.access( TIFF_PREFIX, os.W_OK ):
    sys.exit( f'Unable to write to output directory {TIFF_PREFIX}' )



# Authentication function using "Authorization: Bearer xxx" HTTP header
def authenticate():
    # Only if we have defined a token
    if token:
        if request.headers.get('Authorization'):
            authorization = request.headers.get('Authorization')
            tokens = authorization.split(" ")
            if tokens[0] != "Bearer" or tokens[1] != token:
                abort( 401 )
        else:
                abort( 401 )



# Default route
@app.route("/")
def index():
    return "<!DOCTYPE html><html><head><style>body {margin: 0;height: 100vh;display: grid;place-items: center;}h1 {width: auto;height:6em;background-color: #7f0000;color: white;text-align: center;line-height:6em;padding: 0 2em;box-shadow:0.2em 0.2em 0.5em gray;border-radius:0.4em}</style></head><body><h1>REST IIIF Image API end-point</h1></body></html>"



# Convert a list of images supplied as a JSON array
@app.route("/", methods=['PUT'])
def convert_all():

    images = request.json
    results = []
    status = 200
    for image in images:
        response = convert( image )

        # Check for errors
        if response[1] != 200:
            status = 500

        results.append( response[0] )

    # Return an array of statuses
    return( results, status, {'Content-Type': 'application/json'} )



# Delete a list of images supplied as a JSON array
@app.route("/", methods=['DELETE'])
def delete_all():

    images = request.json
    results = []
    status = 200
    for image in images:
        response = delete( image )

        # Check for errors
        if response[1] != 200:
            status = 500

        results.append( response[0] )

    # Return an array of statuses
    return( results, status, {'Content-Type': 'application/json'} )



# Whether image exists (header-only response)
@app.route("/<path:name>", methods=['HEAD'])
def exists( name ):

    image = f'{TIFF_PREFIX}{name}.tif'
    # Check image exists
    if os.access( image, os.R_OK ):
        return ('', 200)
    else:
        return ('', 404)



# Convert single image
@app.route("/<path:name>", methods=['PUT'])
def convert(name):

    authenticate()

    # Set compression
    compression = COMPRESSION
    if request.args.get('compression') in ['none','deflate','jpeg','webp','lzw','zstd']:
        compression = request.args.get('compression')

    # Set quality level
    quality = QUALITY
    if request.args.get('quality'):
        quality = request.args.get('quality')

    # Set tile size
    tilesize = TILESIZE
    if request.args.get('tilesize'):
        tilesize = request.args.get('tilesize')


    # Time our transcoding
    start = perf_counter()


    try:

        image = f'{PREFIX}{name}'
        output = f'{TIFF_PREFIX}{name}.tif'
        keep = True

        # Check whether output image already exists
        if os.access( output, os.W_OK ):
            im = pyvips.Image.new_from_file( output )
            width = im.width
            height = im.height
            size = os.path.getsize( output )
            if size == 0:
                raise Exception( 'Empty output TIFF' )
            return {
                "image": name,
                "width": width,
                "height": height,
                "bytes": size,
                "time": 0
            }, 200
        

        # If input does not exist locally and S3 has been setup, download image
        if s3 and bucket and not os.access( image, os.R_OK ):

            # Download from S3
            with open( image, 'wb' ) as data:
                bucket.download_fileobj( name, data )

            keep = False # Remove local copy after processing
            size = os.path.getsize( image )
            print( f'Downloaded {name} of size {size} bytes from S3' )

            if size == 0:
                raise Exception( f'Error downloading {name} from S3' )


        # Check image exists and is readable
        if not os.access( image, os.R_OK ):
            raise FileNotFoundError( f'Input image not readable' )


        # Open image with vips
        im = pyvips.Image.new_from_file( image )
        width = im.width
        height = im.height


        # Handle 1 band images when using webp compression
        if im.bands == 1 and compression == 'webp':
            im = im.bandjoin([im,im]).copy(interpretation='rgb')

        im.tiffsave( output, compression=compression, tile=True,
                     tile_width=tilesize, tile_height=tilesize, Q=quality,
                     pyramid=True )

        end = perf_counter()

        # Check output size
        size = os.path.getsize( output )
        if size == 0:
            raise Exception( 'Empty output TIFF' )


        # Delete local copy of input file if asked to
        if not keep:
            os.remove( image )

        return {
            "image": name,
            "width": width,
            "height": height,
            "bytes": size,
            "compression": compression,
            "quality": quality,
            "time": end-start
        }, 200



    # Handle exceptions
    except FileNotFoundError as err:
        if not keep:
            os.remove( image )

        return {
            "image": name,
            "error": err.args[0],
            "action": "convert",
            "time": perf_counter()-start,
            "success": False
        }, 404

    except botocore.exceptions.ClientError as err:
        if not keep:
            os.remove( image )

        return {
            "image": name,
            "error": f'S3 error when downloading {image}: {err.args[0]}',
            "action": "convert",
            "time": perf_counter()-start,
            "success": False
        }, 500

    except Exception as err:
        if not keep:
            os.remove( image )

        return {
            "image": name,
            "error": f'Error converting image {image}: {err.args[0]}',
            "action": "convert",
            "time": perf_counter()-start,
            "success": False
        }, 500



# Delete image
@app.route('/<path:name>', methods=['DELETE'])
def delete(name):

    authenticate()

    image = f'{TIFF_PREFIX}{name}.tif'

    try:
        # Check image exists
        if not os.access( image, os.R_OK ):
            # If no suffix has been supplied, perform globbing
            pattern = f'{TIFF_PREFIX}{name}.*.tif'
            images = glob.glob( pattern )
            if len(images) > 0:
                image = images[0]   # Assume only 1 image for the moment
            else:
                raise FileNotFoundError( pattern )


        # Check image is writable
        if not os.access( image, os.W_OK ):
            raise Exception( 'Output image not writable' )

        os.remove( image )
        return {
            "image": image,
            "action": "delete",
            "success": True
        }, 200


    # Handle exceptions
    except FileNotFoundError as err:
        return {
            "image": name,
            "error": err.args[0],
            "action": "delete",
            "success": False
        }, 404

    except Exception as err:
        return {
            "image": image,
            "action": "delete",
            "success": False,
            "error": err.args[0]
        }, 500



