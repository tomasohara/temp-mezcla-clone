#! /usr/bin/env python
#
# Illustrates how to use Stable Diffusion via Hugging Face (HF) diffusers package,
# including gradio-based UI.
#
# via https://huggingface.co/spaces/stabilityai/stable-diffusion
# also uses https://huggingface.co/CompVis/stable-diffusion-v1-4
# and https://stackoverflow.com/questions/48273205/accessing-incoming-post-data-in-flask
#
# This was designed originally for text-to-image (i.e., from prompt to image).
# However, it has been adapted to support image-to-image as well, which includes an image
# input along the prompt(s).
#
# Support is also included for clip interrogation, which is not yet part of a HF API
#
# Note:
# - For tips on parameter settings, see
#   https://getimg.ai/guides/interactive-guide-to-stable-diffusion-guidance-scale-parameter
# - For a full-featured interface to Stable Diffusion, see
#   https://github.com/AUTOMATIC1111/stable-diffusion-webui
# - For a stylish Stable Diffusion interface, see
#   https://github.com/comfyanonymous/ComfyUI
#
# TODO:
# - Set GRADIO_SERVER_NAME to 0.0.0.0?
#

"""Image generation via HF Stable Diffusion (SD) API"""

# Standard modules
import base64
from io import BytesIO
import json
import time

# Installed modules
import diskcache
from flask import Flask, request
import PIL
import requests
## OLD: import gradio as gr
gr = None

# Local modules
from mezcla import debug
from mezcla import glue_helpers as gh
from mezcla.main import Main
from mezcla.my_regex import my_re
from mezcla import system

# Constants/globals
TL = debug.TL
PROMPT = system.getenv_text("PROMPT", "your favorite politician in a tutu",
                            "Textual prompt describing image")
NEGATIVE_PROMPT = system.getenv_text("NEGATIVE_PROMPT", "photo realistic",
                            "Negative tips for image")
GUIDANCE_HELP = "Degree of fidelity to prompt (1-to-30 w/ 7 suggested)--higher more"
GUIDANCE_SCALE = system.getenv_int("GUIDANCE_SCALE", 7,
                                   ## OLD: "How much the image generation follows the prompt")
                                   description=GUIDANCE_HELP)
SD_URL = system.getenv_value("SD_URL", None,
                             "URL for SD TCP/restful server--new via flask or remote")
SD_PORT = system.getenv_int("SD_PORT", 9700,
                            "TCP port for SD server")
SD_DEBUG = system.getenv_int("SD_DEBUG", False,
                             "Run SD server in debug mode")
USE_HF_API = system.getenv_bool("USE_HF_API", not SD_URL,
                                "Use Huggingface API instead of TCP server")
CHECK_UNSAFE = system.getenv_bool("CHECK_UNSAFE", False,
                                  "Apply unsafe word list regex filter")
NUM_IMAGES = system.getenv_int("NUM_IMAGES", 1,
                               "Number of images to generated")
BASENAME = system.getenv_text("BASENAME", "sd-app-image",
                              "Basename for saving images")
FULL_PRECISION = system.getenv_bool("FULL_PRECISION", False,
                                    "Use full precision GPU computations")
LOW_MEMORY = system.getenv_bool("LOW_MEMORY", (not FULL_PRECISION),
                                "Use low memory computations such as via float16")
DUMMY_RESULT = system.getenv_bool("DUMMY_RESULT", False,
                                  "Mock up SD server result")
DISK_CACHE = system.getenv_value("SD_DISK_CACHE", None,
                                 "Path to directory with disk cache")
USE_IMG2IMG = system.getenv_bool("USE_IMG2IMG", False,
                                 "Use image-to-image instead of text-to-image")
DENOISING_FACTOR = system.getenv_float("DENOISING_FACTOR", 0.75,
                                       "How much of the input image to randomize--higher more")

BATCH_ARG = "batch"
SERVER_ARG = "server"
UI_ARG = "UI"
PORT_ARG = "port"
PROMPT_ARG = "prompt"
NEGATIVE_ARG = "negative"
GUIDANCE_ARG = "guidance"
## TODO?: TXT2IMG_ARG = "txt2img"
IMG2IMG_ARG = "img2img"
IMAGE_ARG = "input-image"
DENOISING_ARG = "denoising-factor"
DUMMY_BASE64_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAA8AAAAPAgMAAABGuH3ZAAAADFBMVEUAAMzMzP////8AAABGA1scAAAAJUlEQVR4nGNgAAFGQUEowRoa6sCABBZowAgsgBEIGUQCRALAPACMHAOQvR4HGwAAAABJRU5ErkJggg=="
DUMMY_IMAGE_FILE = gh.resolve_path("dummy-image.png")
HTTP_OK = 200

# Conditional imports for HF/PyTorch
torch = None
load_dataset = None
if USE_HF_API:
    # pylint: disable=import-outside-toplevel, import-error
    from datasets import load_dataset
    import torch

word_list = []
if CHECK_UNSAFE:
    word_list_dataset = load_dataset("stabilityai/word-list", data_files="list.txt", use_auth_token=True)
    word_list = word_list_dataset["train"]['text']
    debug.trace_expr(5, word_list)

sd_instance = None
flask_app = Flask(__name__)


def show_gpu_usage(level=TL.DETAILED):
    """Show usage for GPU memory, etc.
    TODO: support other types besides NVidia"""
    debug.trace(level, "GPU usage")
    debug.trace(level, gh.run("nvidia-smi"))

#-------------------------------------------------------------------------------
# Main Stable Diffusion support

class StableDiffusion:
    """Class providing Stable Diffusion generative AI (e.g., text-to-image)"""

    def __init__(self, use_hf_api=None, server_url=None, server_port=None, low_memory=None):
        debug.trace(4, f"{self.__class__.__name__}.__init__{(use_hf_api, server_url, server_port)}")
        if use_hf_api is None:
            use_hf_api = USE_HF_API
        self.use_hf_api = use_hf_api
        if (server_url is None) and (not self.use_hf_api):
            server_url = SD_URL
        self.server_url = server_url
        if server_port is None:
            server_port = SD_PORT
        if self.server_url and not my_re.search(r"^https?", self.server_url):
            # note: remote flask server (e.g., on GPU server)
            self.server_url = f"http://{self.server_url}"
            debug.trace(4, f"Added http protocol to URL: {self.server_url}")
        if self.server_url:
            if not my_re.search(r":\d+", self.server_url):
                # TODO3: http://base-url/path => http://base-url:port/path
                self.server_url += f":{server_port}"
            else:
                system.print_stderr(f"Warning: ignoring port {server_port} as already in URL {self.server_url}")
        elif self.use_hf_api:
            pass
        else:
            debug.trace(4,"Warning: Unexpected condition in {self.__class__.__name__}.__init__: no server_url")
        if low_memory is None:
            low_memory = LOW_MEMORY
        self.low_memory = low_memory
        self.pipe = None
        self.img2txt_engine = None
        self.cache = None
        if DISK_CACHE:
            self.cache = diskcache.Cache(
                DISK_CACHE,                   # path to dir
                disk=diskcache.core.JSONDisk, # avoid serialization issue
                disk_compress_level=0,        # no compression
                cull_limit=0)                 # no automatic pruning
        debug.assertion(bool(self.use_hf_api) != bool(self.server_url))
        debug.trace_object(5, self, label=f"{self.__class__.__name__} instance")
    
    def init_pipeline(self, txt2img=None, img2img=None):
        """Initialize Stable Diffusion"""
        debug.trace(4, "init_pipeline()")
        debug.assertion(not (txt2img and img2img))
        debug.assertion(not img2img)
        # pylint: disable=import-outside-toplevel
        from diffusers import StableDiffusionPipeline
        model_id = "CompVis/stable-diffusion-v1-4"
        device = "cuda"
        # TODO2: automatically use LOW_MEMORY if GPU memory below 8gb
        dtype=(torch.float16 if self.low_memory else None)
        pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=dtype)
        debug.trace_expr(5, pipe, dtype)
        pipe = pipe.to(device)
        pipe.set_progress_bar_config(disable=True)
        pipe.enable_attention_slicing()
        debug.trace_object(6, pipe)
        show_gpu_usage()
        return pipe

    def init_txt2img(self):
        """Initialize Stable Diffusion text-to-image support (i.e., txt2img)"""
        debug.trace(4, "init_txt2img()")
        return self.init_pipeline(txt2img=True)

    def init_img2img(self):
        """Initialize Stable Diffusion image-to-image support (i.e., img2img)"""
        debug.trace(4, "init_img2img()")
        # pylint: disable=import-outside-toplevel
        from diffusers import StableDiffusionImg2ImgPipeline
        # TODO2: v1-5
        model_id = "CompVis/stable-diffusion-v1-4"
        device = "cuda"
        # TODO2: automatically use LOW_MEMORY if GPU memory below 8gb
        dtype=(torch.float16 if self.low_memory else None)
        pipe = StableDiffusionImg2ImgPipeline.from_pretrained(model_id, torch_dtype=dtype)
        debug.trace_expr(5, pipe, dtype)
        pipe = pipe.to(device)
        pipe.set_progress_bar_config(disable=True)
        pipe.enable_attention_slicing()
        debug.trace_object(6, pipe)
        show_gpu_usage()
        return pipe

    def init_clip_interrogation(self):
        """Initialize CLIP interrogation for use with Stable Diffusion"""
        # pylint: disable=import-outside-toplevel
        from clip_interrogator import Config, Interrogator
        self.img2txt_engine = Interrogator(Config(clip_model_name="ViT-L-14/openai"))
    
    def infer(self, prompt=None, negative_prompt=None, scale=None, num_images=None,
              skip_img_spec=False, width=None, height=None):
        """Generate images using positive PROMPT and NEGATIVE one, along with guidance SCALE,
        and targetting a WIDTHxHEIGHT image.
        Returns list of NUM image specifications in base64 format (e.g., for use in HTML).
        Note: If SKIP_IMG_SPEC specified, result is formatted for HTML IMG tag
        """
        ## OLD: debug.trace(4, f"{self.__class__.__name__}.infer{(prompt, negative_prompt, scale, num_images)}")
        debug.trace_expr(4, prompt, negative_prompt, scale, num_images, skip_img_spec, prefix=f"\nin {self.__class__.__name__}.infer:\n\t", delim="\n\t",  suffix="}\n", max_len=1024)
        if num_images is None:
            num_images = NUM_IMAGES
        if scale is None:
            scale = GUIDANCE_SCALE
        for prompt_filter in word_list:
            if my_re.search(rf"\b{prompt_filter}\b", prompt):
                ## OLD: raise gr.Error("Unsafe content found. Please try again with different prompts.")
                raise RuntimeError("Unsafe content found. Please try again with different prompts.")
    
        images = []
        params = (prompt, negative_prompt, scale, num_images, skip_img_spec, width, height)

        if self.cache is not None:
            images = self.cache.get(params)
        if images and len(images) > 0:
            ## TEST:
            ## debug.trace_fmt(6, "Using cached result for params {p}: ({r})",
            ##                 p=params, r=images)
            debug.trace_fmt(5, "Using cached infer result: ({r})", r=images)
        else:
            images = self.infer_non_cached(*params)
            if self.cache is not None:
                self.cache.set(params, images)
                debug.trace_fmt(6, "Setting cached result (r={r})", r=images)
        return images

    def infer_non_cached(self, prompt=None, negative_prompt=None, scale=None, num_images=None,
                         skip_img_spec=False, width=None, height=None):
        """Non-cached version of infer"""
        params = (prompt, negative_prompt, scale, num_images, skip_img_spec, width, height)
        debug.trace(5, f"{self.__class__.__name__}.infer_non_cached{params}")
        images = []
        if self.use_hf_api:
            if DUMMY_RESULT:
                result = [DUMMY_BASE64_IMAGE]
                debug.trace(5, f"early exit infer_non_cached() => {result}")
                return result

            if not self.pipe:
                self.pipe = self.init_pipeline()
            start_time = time.time()
            image_info = self.pipe(prompt, negative_prompt=negative_prompt, guidance_scale=scale,
                                   num_images_per_prompt=num_images, width=width, height=height)
            debug.trace_expr(4, image_info)
            debug.trace_object(5, image_info, "image_info")
            num_generated = 0
            for i, image in enumerate(image_info.images):
                debug.trace_expr(4, image)
                debug.trace_object(5, image, "image")
                b64_encoding = image
                debug.assertion(isinstance(image, PIL.Image.Image))
                try:
                    image_path = f"{BASENAME}-{i + 1}.png"
                    image.save(image_path)
                    num_generated += 1
                    # note: "decodes" base-64 encoded bytes object into UTF-8 string
                    b64_encoding = (base64.b64encode(system.read_binary_file(image_path))).decode()
                    if not skip_img_spec:
                        b64_encoding = (f"data:image/png;base64,{b64_encoding}")
                except:
                    system.print_exception_info("image-to-base64")
                images.append(b64_encoding)
            elapsed = round(time.time() - start_time, 3)
            debug.trace(4, f"{elapsed} seconds to generate {num_images} images")
            debug.assertion(num_generated == num_images)
            show_gpu_usage()
        else:
            debug.assertion(self.server_url)
            url = self.server_url
            payload = {'prompt': prompt, 'negative_prompt': negative_prompt, 'scale': scale,
                       'num_images': num_images}
            images_request = requests.post(url, json=payload, timeout=(5 * 60))
            debug.trace_object(6, images_request)
            debug.trace_expr(5, payload, images_request, images_request.json(), delim="\n")
            for image in images_request.json()["images"]:
                image_b64 = image
                if not skip_img_spec:
                    image_b64 = (f"data:image/png;base64,{image_b64}")
                images.append(image_b64)
        result = images
        debug.trace_fmt(5, "infer_non_cached() => {r!r}", r=result)
        return result

    def infer_img2img(self, image_b64=None, denoise=None,  prompt=None, negative_prompt=None, scale=None, num_images=None,
                      skip_img_spec=False):
        """Generate images from IMAGE_B64 using positive PROMPT and NEGATIVE one, along with guidance SCALE and NUM_IMAGES
        Returns list of NUM image specifications in base64 format (e.g., for use in HTML).
        Note: If SKIP_IMG_SPEC specified, result is formatted for HTML IMG tag
        """
        debug.trace_expr(4, image_b64, denoise, prompt, negative_prompt, scale, num_images, skip_img_spec, prefix=f"\nin {self.__class__.__name__}.infer_img2img: {{\n\t", delim="\n\t", suffix="}\n", max_len=1024)
        if num_images is None:
            num_images = NUM_IMAGES
        if scale is None:
            scale = GUIDANCE_SCALE
        if denoise is None:
            denoise = DENOISING_FACTOR
        for prompt_filter in word_list:
            if my_re.search(rf"\b{prompt_filter}\b", prompt):
                raise RuntimeError("Unsafe content found. Please try again with different prompts.")
    
        images = []
        params = (image_b64, denoise, prompt, negative_prompt, scale, num_images, skip_img_spec)

        if self.cache is not None:
            images = self.cache.get(params)
        if images and len(images) > 0:
            ## TEST:
            ## debug.trace_fmt(6, "Using cached result for params {p}: ({r})",
            ##                 p=params, r=images)
            debug.trace_fmt(5, "Using cached infer result: ({r})", r=images)
        else:
            images = self.infer_img2img_non_cached(*params)
            if self.cache is not None:
                self.cache.set(params, images)
                debug.trace_fmt(6, "Setting cached result (r={r})", r=images)
        return images

    def infer_img2img_non_cached(self, image_b64=None, denoise=None, prompt=None, negative_prompt=None, scale=None, num_images=None,
                                 skip_img_spec=False):
        """Non-cached version of infer_img2img"""
        params = (image_b64, denoise, prompt, negative_prompt, scale, num_images, skip_img_spec)
        params_spec = params
        if debug.detailed_debugging():
            params_spec = tuple(map(gh.elide, params))
        debug.trace(5, f"{self.__class__.__name__}.infer_img2img_non_cached{params_spec}")
        images = []
        if self.use_hf_api:
            if DUMMY_RESULT:
                result = ["iVBORw0KGgoAAAANSUhEUgAAAA8AAAAPAgMAAABGuH3ZAAAADFBMVEUAAMzMzP////8AAABGA1scAAAAJUlEQVR4nGNgAAFGQUEowRoa6sCABBZowAgsgBEIGUQCRALAPACMHAOQvR4HGwAAAABJRU5ErkJggg=="]
                debug.trace(5, f"early exit infer_img2img_non_cached() => {result}")
                return result

            if not self.pipe:
                self.pipe = self.init_img2img()
            # Get input image
            input_image = create_image(decode_base64_image(image_b64))
            # Generate derived output images(s)
            image_info = self.pipe(image=input_image, strength=denoise, prompt=prompt, negative_prompt=negative_prompt, guidance_scale=scale,
                                   num_images_per_prompt=num_images)
            debug.trace_expr(4, image_info)
            debug.trace_object(5, image_info, "image_info")
            start_time = time.time()
            num_generated = 0
            for i, image in enumerate(image_info.images):
                debug.trace_expr(4, image)
                debug.trace_object(5, image, "image")
                b64_encoding = image
                debug.assertion(isinstance(image, PIL.Image.Image))
                try:
                    image_path = f"{BASENAME}-{i + 1}.png"
                    image.save(image_path)
                    num_generated += 1
                    # note: "decodes" base-64 encoded bytes object into UTF-8 string
                    b64_encoding = (base64.b64encode(system.read_binary_file(image_path))).decode()
                    if not skip_img_spec:
                        b64_encoding = (f"data:image/png;base64,{b64_encoding}")
                except:
                    system.print_exception_info("image-to-base64")
                images.append(b64_encoding)
            elapsed = round(time.time() - start_time, 3)
            debug.trace(4, f"{elapsed} seconds to derive {num_images} images")
            debug.assertion(num_generated == num_images)
            show_gpu_usage()
        else:
            debug.assertion(self.server_url)
            url = self.server_url
            payload = {'input_image': input_image, 'strength': denoise, 'prompt': prompt, 'negative_prompt': negative_prompt, 'scale': scale,
                       'num_images': num_images}
            images_request = requests.post(url, json=payload, timeout=(5 * 60))
            debug.trace_object(6, images_request)
            debug.trace_expr(5, payload, images_request, images_request.json(), delim="\n")
            for image in images_request.json()["images"]:
                image_b64 = image
                if not skip_img_spec:
                    image_b64 = (f"data:image/png;base64,{image_b64}")
                images.append(image_b64)
        result = images
        debug.trace_fmt(5, "infer_img2img_non_cached() => {r!r}", r=result)
        
        return result

    def infer_img2txt(self, image_b64=None):
        """Return likely caption text for image_b64 in base64 encoding"""
        debug.trace_fmt(4, f"infer_img2txt({gh.elide(image_b64)})")
        params = (image_b64)
        description = ""
        if self.cache is not None:
            description = self.cache.get(params)
        if not description:
            description = self.infer_img2txt_non_cached(image_b64)
            if self.cache is not None:
                self.cache.set(params, description)
                debug.trace_fmt(6, "Setting cached result (r={r!r})", r=description)

        return description
    
    def infer_img2txt_non_cached(self, image_b64=None):
        """Non-cached version of infer_img2txt"""
        # Get input image and infer likely caption text
        image = create_image(decode_base64_image(image_b64))
        if not self.img2txt_engine:
            self.init_clip_interrogation()
        image_caption = self.img2txt_engine.interrogate(image)
        debug.trace_fmt(5, "infer_img2txt_non_cached() => {r!r}", r=image_caption)
        return image_caption
    
#-------------------------------------------------------------------------------
# Middleware

@flask_app.route('/', methods=['GET', 'POST'])
def handle_infer():
    """Process request to do inference to generate image from text"""
    debug.trace(6, "[flask_app /] handle_infer()")
    # TODO3: request => flask_request
    debug.trace_object(5, request)
    params = request.get_json()
    debug.trace_expr(5, params)
    images_spec = {"images": sd_instance.infer(**params)}
    # note: see https://stackoverflow.com/questions/45412228/sending-json-and-status-code-with-a-flask-response
    result = (json.dumps(images_spec), HTTP_OK)
    debug.trace_object(7, result)
    debug.trace_fmt(7, "handle_infer() => {r}", r=result)
    return result


@flask_app.route('/txt2img', methods=['GET', 'POST'])
def handle_infer_txt2img():
    """Process request to do inference to generate image from text"""
    debug.trace(6, "[flask_app /] handle_infer_txt2img()")
    return handle_infer()
    

def infer(prompt=None, negative_prompt=None, scale=None, num_images=None, skip_img_spec=None):
    """Wrapper around StableDiffusion.infer()
    Note: intended just for the gradio UI"
    """
    debug.trace(5, f"[sd_instance] infer{(prompt, negative_prompt, scale, skip_img_spec)}")
    return sd_instance.infer(prompt=prompt, negative_prompt=negative_prompt, scale=scale, num_images=num_images, skip_img_spec=skip_img_spec)


@flask_app.route('/img2img', methods=['GET', 'POST'])
def handle_infer_img2img():
    """Process request to do inference to generate similar image from existing image"""
    debug.trace(6, "[flask_app /] handle_infer_img2img()")
    # TODO3: request => flask_request
    debug.trace_object(5, request)
    params = request.get_json()
    debug.trace_expr(5, params)
    images_spec = {"images": sd_instance.infer_img2img(**params)}
    # note: see https://stackoverflow.com/questions/45412228/sending-json-and-status-code-with-a-flask-response
    result = (json.dumps(images_spec), HTTP_OK)
    debug.trace_object(7, result)
    debug.trace_fmt(7, "handle_infer_img2img() => {r}", r=result)
    return result


def infer_img2img(image_spec=None, denoise=None,  prompt=None, negative_prompt=None, scale=None, num_images=None, skip_img_spec=None):
    """Wrapper around StableDiffusion.infer_img2img()
    Note: intended just for the gradio UI"
    """
    image_b64 = None
    if isinstance(image_spec, list):
        debug.trace(5, "Warning: using first image in image_spec for infer_img2img")
        image_spec = image_spec[0]
    if ((image_spec is not None) and (not isinstance(image_spec, str))):
        ## TODO?: image = PIL.Image.fromarray(image_spec, mode="RGB")
        debug.trace_expr(7, image_spec)
        image = (image_spec)
        image_b64 = encode_PIL_image(image)
    debug.trace(5, f"[sd_instance] infer_img2img{(gh.elide(image_spec), denoise, prompt, negative_prompt, scale, skip_img_spec)}")
    return sd_instance.infer_img2img(image_b64=image_b64, denoise=denoise, prompt=prompt, negative_prompt=negative_prompt, scale=scale, num_images=num_images, skip_img_spec=skip_img_spec)


def infer_img2txt(image_spec):
    """Wrapper around StableDiffusion.infer_img2txt()
    Note: intended just for the gradio UI"
    """
    debug.trace(5, f"[sd_instance] infer_img2txt({gh.elide(image_spec)})")
    image_b64 = encode_PIL_image(image_spec)
    return sd_instance.infer_img2txt(image_b64)

#--------------------------------------------------------------------------------
# Utility functions

def encode_image_data(image_bytes):
    """Convert IMAGE_BYTES to base64 string"""
    debug.assertion(isinstance(image_bytes, bytes))
    result = base64.b64encode(image_bytes).decode()
    debug.trace(6, f"encode_image_data({gh.elide(image_bytes)}) => {gh.elide(result)}")
    return result

def encode_image_file(filename):
    """Encode image in FILENAME via base64 string"""
    binary_data = system.read_binary_file(filename)
    result = encode_image_data(binary_data)
    debug.trace(6, f"encode_image_file({filename}) => {gh.elide(result)}")
    return result

def encode_PIL_image(image):
    """Convert from PIL image into base64"""
    debug.assertion(isinstance(image, PIL.Image.Image))
    ## BAD: result = encode_image_data(image.tobytes())
    ## note: all sorts of silly issues with PIL!
    bytes_fh = BytesIO()
    image.save(bytes_fh, format="PNG")
    bytes_fh.seek(0)
    result = encode_image_data(bytes_fh.read())
    debug.trace(6, f"encode_PIL_image({gh.elide(image)}) => {gh.elide(result)}")
    return result

def decode_base64_image(image_encoding):
    """Decode IMAGE_ENCODING from base64 returning bytes"""
    # note: "encodes" UTF-8 text of base-64 encoding as bytes object for str, and then decodes into image bytes
    result = base64.decodebytes(image_encoding.encode())
    debug.trace(6, f"decode_base64_image({gh.elide(image_encoding)}) => {gh.elide(result)}")
    return result

def create_image(image_data):
    """Create PIL image from IMAGE_DATA bytes"""
    result = PIL.Image.open(BytesIO(image_data)).convert("RGB")
    debug.trace(6, f"create_image({image_data!r}) => {result}")
    return result

def write_image_file(filename, image_spec):
    """Write to FILENAME the base64 data in IMAGE_SPEC"""
    debug.trace(5, f"write_image_file({filename}, {image_spec})")
    system.write_binary_file(filename, decode_base64_image(image_spec))

#-------------------------------------------------------------------------------
# User interface

def upload_image(upload_control):
    """Upload image data from UPLOAD_CONTROL returning base64 encoded image"""
    debug.trace(4, f"upload_image({upload_control})")
    debug.trace_object(5, upload_control)
    encoded_image = encode_image_file(upload_control.value)
    return encoded_image


def upload_image_file(files):
    """Return path for each of the FILES"""
    debug.trace(4, f"upload_image_file({files})")
    images = [encode_image_file(file.name) for file in files]
    return images


def run_ui(use_img2img=None):
    """Run user interface via gradio serving by default at localhost:7860
    Note: The environment variable GRADIO_SERVER_NAME can be used to serve via 0.0.0.0"""
    import gradio as gr                 # pylint: disable=import-outside-toplevel, redefined-outer-name
    css = """
            .gradio-container {
                font-family: 'IBM Plex Sans', sans-serif;
            }
            .gr-button {
                color: white;
                border-color: black;
                background: black;
            }
            input[type='range'] {
                accent-color: black;
            }
            .dark input[type='range'] {
                accent-color: #dfdfdf;
            }
            .container {
                max-width: 730px;
                margin: auto;
                padding-top: 1.5rem;
            }
            #gallery {
                min-height: 22rem;
                margin-bottom: 15px;
                margin-left: auto;
                margin-right: auto;
                border-bottom-right-radius: .5rem !important;
                border-bottom-left-radius: .5rem !important;
            }
            #gallery>div>.h-full {
                min-height: 20rem;
            }
            .details:hover {
                text-decoration: underline;
            }
            .gr-button {
                white-space: nowrap;
            }
            .gr-button:focus {
                border-color: rgb(147 197 253 / var(--tw-border-opacity));
                outline: none;
                box-shadow: var(--tw-ring-offset-shadow), var(--tw-ring-shadow), var(--tw-shadow, 0 0 #0000);
                --tw-border-opacity: 1;
                --tw-ring-offset-shadow: var(--tw-ring-inset) 0 0 0 var(--tw-ring-offset-width) var(--tw-ring-offset-color);
                --tw-ring-shadow: var(--tw-ring-inset) 0 0 0 calc(3px var(--tw-ring-offset-width)) var(--tw-ring-color);
                --tw-ring-color: rgb(191 219 254 / var(--tw-ring-opacity));
                --tw-ring-opacity: .5;
            }
            #advanced-btn {
                font-size: .7rem !important;
                line-height: 19px;
                margin-top: 12px;
                margin-bottom: 12px;
                padding: 2px 8px;
                border-radius: 14px !important;
            }
            #advanced-options {
                display: none;
                margin-bottom: 20px;
            }
            .footer {
                margin-bottom: 45px;
                margin-top: 35px;
                text-align: center;
                border-bottom: 1px solid #e5e5e5;
            }
            .footer>p {
                font-size: .8rem;
                display: inline-block;
                padding: 0 10px;
                transform: translateY(10px);
                background: white;
            }
            .dark .footer {
                border-color: #303030;
            }
            .dark .footer>p {
                background: #0b0f19;
            }
            .acknowledgments h4{
                margin: 1.25em 0 .25em 0;
                font-weight: bold;
                font-size: 115%;
            }
            .animate-spin {
                animation: spin 1s linear infinite;
            }
            @keyframes spin {
                from {
                    transform: rotate(0deg);
                }
                to {
                    transform: rotate(360deg);
                }
            }
            #share-btn-container {
                display: flex; padding-left: 0.5rem !important; padding-right: 0.5rem !important; background-color: #000000; justify-content: center; align-items: center; border-radius: 9999px !important; width: 13rem;
                margin-top: 10px;
                margin-left: auto;
            }
            #share-btn {
                all: initial; color: #ffffff;font-weight: 600; cursor:pointer; font-family: 'IBM Plex Sans', sans-serif; margin-left: 0.5rem !important; padding-top: 0.25rem !important; padding-bottom: 0.25rem !important;right:0;
            }
            #share-btn * {
                all: unset;
            }
            #share-btn-container div:nth-child(-n+2){
                width: auto !important;
                min-height: 0px !important;
            }
            #share-btn-container .wrap {
                display: none !important;
            }
            
            .gr-form{
                flex: 1 1 50%; border-top-right-radius: 0; border-bottom-right-radius: 0;
            }
            #prompt-container{
                gap: 0;
            }
            #prompt-text-input, #negative-prompt-text-input{padding: .45rem 0.625rem}
            #component-16{border-top-width: 1px!important;margin-top: 1em}
            .image_duplication{position: absolute; width: 100px; left: 50px}
    """
    
    block = gr.Blocks(css=css, title="HF Stable Diffusion gradio UI")

    # note: [prompt, negative, guidance]
    txt2img_examples = [
        [
            'A high tech solarpunk utopia in the Amazon rainforest',
            'low quality',
            9, 
        ],
        [
            'A pikachu fine dining with a view to the Eiffel Tower',
            'low quality',
            9, 
        ],
        [
            'A mecha robot in a favela in expressionist style',
            'low quality, 3d, photorealistic',
            9, 
        ],
        [
            'an insect robot preparing a delicious meal',
            'low quality, illustration',
            9,
        ],
    ]
    
    # note: [input_img, denoise_factor, prompt, negative, guidance ]
    img2img_examples = [
        ## TEST: [ DUMMY_BASE64_IMAGE, 0.75, 'A modern Pacman', 'retro', 7, ],
        [ DUMMY_IMAGE_FILE, 0.75, 'A modern Pacman', 'retro', 7, ],
    ]
    

    # Specify CSS styles and SVG data (TODO3: for what?)
    with block:
        gr.HTML(
            """
                <div style="text-align: center; margin: 0 auto;">
                  <div
                    style="
                      display: inline-flex;
                      align-items: center;
                      gap: 0.8rem;
                      font-size: 1.75rem;
                    "
                  >
                    <svg
                      width="0.65em"
                      height="0.65em"
                      viewBox="0 0 115 115"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <rect width="23" height="23" fill="white"></rect>
                      <rect y="69" width="23" height="23" fill="white"></rect>
                      <rect x="23" width="23" height="23" fill="#AEAEAE"></rect>
                      <rect x="23" y="69" width="23" height="23" fill="#AEAEAE"></rect>
                      <rect x="46" width="23" height="23" fill="white"></rect>
                      <rect x="46" y="69" width="23" height="23" fill="white"></rect>
                      <rect x="69" width="23" height="23" fill="black"></rect>
                      <rect x="69" y="69" width="23" height="23" fill="black"></rect>
                      <rect x="92" width="23" height="23" fill="#D9D9D9"></rect>
                      <rect x="92" y="69" width="23" height="23" fill="#AEAEAE"></rect>
                      <rect x="115" y="46" width="23" height="23" fill="white"></rect>
                      <rect x="115" y="115" width="23" height="23" fill="white"></rect>
                      <rect x="115" y="69" width="23" height="23" fill="#D9D9D9"></rect>
                      <rect x="92" y="46" width="23" height="23" fill="#AEAEAE"></rect>
                      <rect x="92" y="115" width="23" height="23" fill="#AEAEAE"></rect>
                      <rect x="92" y="69" width="23" height="23" fill="white"></rect>
                      <rect x="69" y="46" width="23" height="23" fill="white"></rect>
                      <rect x="69" y="115" width="23" height="23" fill="white"></rect>
                      <rect x="69" y="69" width="23" height="23" fill="#D9D9D9"></rect>
                      <rect x="46" y="46" width="23" height="23" fill="black"></rect>
                      <rect x="46" y="115" width="23" height="23" fill="black"></rect>
                      <rect x="46" y="69" width="23" height="23" fill="black"></rect>
                      <rect x="23" y="46" width="23" height="23" fill="#D9D9D9"></rect>
                      <rect x="23" y="115" width="23" height="23" fill="#AEAEAE"></rect>
                      <rect x="23" y="69" width="23" height="23" fill="black"></rect>
                    </svg>
                    <h1 style="font-weight: 900; margin-bottom: 7px;margin-top:5px">
                      Stable Diffusion 2.1 Demo
                    </h1>
                  </div>
                  <p style="margin-bottom: 10px; font-size: 94%; line-height: 23px;">
                    Stable Diffusion 2.1 is the latest text-to-image model from StabilityAI. <a style="text-decoration: underline;" href="https://huggingface.co/spaces/stabilityai/stable-diffusion-1">Access Stable Diffusion 1 Space here</a><br>For faster generation and API
                    access you can try
                    <a
                      href="http://beta.dreamstudio.ai/"
                      style="text-decoration: underline;"
                      target="_blank"
                      >DreamStudio Beta</a
                    >.</a>
                  </p>
                </div>
            """
        )

        # Specify the main form
        # TODO3: be consistent in use of xyz_control
        with gr.Group():
            with gr.Box():
                ## TODO: drop 'rounded', border, margin, and other options no longer supported (see log)
                with gr.Row(elem_id="prompt-container").style(mobile_collapse=False, equal_height=True):
                    with gr.Column():
                        prompt_control = gr.Textbox(
                            label="Enter your prompt",
                            show_label=False,
                            max_lines=1,
                            placeholder="Enter your prompt",
                            elem_id="prompt-text-input",
                        ).style(
                            border=(True, False, True, True),
                            rounded=(True, False, False, True),
                            container=False,
                        )
                        negative_control = gr.Textbox(
                            label="Enter your negative prompt",
                            show_label=False,
                            max_lines=1,
                            placeholder="Enter a negative prompt",
                            elem_id="negative-prompt-text-input",
                        ).style(
                            border=(True, False, True, True),
                            rounded=(True, False, False, True),
                            container=False,
                        )
                    btn = gr.Button("Generate image").style(
                        margin=False,
                        rounded=(False, True, True, False),
                        full_width=False,
                    )
    
            gallery = gr.Gallery(
                label="Generated images", show_label=False, elem_id="gallery"
            ).style(grid=[2], height="auto")
    
    
            with gr.Accordion("Advanced settings", open=False):
            #    gr.Markdown("Advanced settings are temporarily unavailable")
            #    samples = gr.Slider(label="Images", minimum=1, maximum=4, value=4, step=1)
            #    steps = gr.Slider(label="Steps", minimum=1, maximum=50, value=45, step=1)
                 guidance_control = gr.Slider(
                    label="Guidance scale", minimum=1, maximum=30, value=GUIDANCE_SCALE, step=0.1
                 )
                 num_control = gr.Slider(
                    label="Number of images", minimum=1, maximum=10, value=2, step=1
                 )
                 img2img_control = gr.Checkbox(label="Use img2img?", value=use_img2img, interactive=True)
                 denoise_control = gr.Slider(label="Denoising factor", minimum=0, maximum=1, value=DENOISING_FACTOR, step=0.05)
                 ## TODO?:
                 input_image_control = gr.Image(label="Input image")  ## TODO?: type='pil'
                 upload_control = gr.UploadButton(label="Upload image", file_types=["image"])
                 interrogate_control = gr.Button(label="CLIP Interrogator")
                 
            #    seed = gr.Slider(
            #        label="Seed",
            #        minimum=0,
            #        maximum=2147483647,
            #        step=1,
            #        randomize=True,
            #    )

            input_controls = [prompt_control, negative_control, guidance_control, num_control]
            output_controls = [gallery]
            infer_fn = infer
            examples = txt2img_examples
            ## OLD: if img2img_control.value:
            if use_img2img:
                infer_fn = infer_img2img
                input_controls = ([input_image_control, denoise_control] + input_controls)
                examples = img2img_examples
            ex = gr.Examples(examples=examples, fn=infer_fn,
                             inputs=input_controls,
                             outputs=output_controls, cache_examples=False)
            ex.dataset.headers = [""]
            negative_control.submit(infer_fn, inputs=input_controls, outputs=output_controls, postprocess=False)
            prompt_control.submit(infer_fn, inputs=input_controls, outputs=output_controls, postprocess=False)
            btn.click(infer_fn, inputs=input_controls, outputs=output_controls, postprocess=False)
            # TODO1: fix
            ## OLD: upload_control.click(fn=upload_image, inputs=[upload_control], outputs=[input_image_control])
            upload_control.upload(fn=upload_image_file, inputs=[upload_control], outputs=[input_image_control],
                                  postprocess=False)
            #
            def change_examples():
                """Change examples used in UI if img2img_control checked"""
                debug.trace(4, "change_examples()")
                debug.trace_object(5, img2img_control)
                ex.examples = (img2img_examples if img2img_control.value else txt2img_examples)
            #
            # TODO2: use one listener
            # TODO1: fix
            img2img_control.change(fn=change_examples, inputs=[], outputs=[])
            img2img_control.select(fn=change_examples, inputs=[], outputs=[])
            #
            def use_clip_for_prompt():
                """Run CLIP interrogator over image and send result to prompt field"""
                debug.trace(4, "use_clip_for_prompt()")
                debug.trace_object(5, input_image_control)
                prompt_control.value = infer_img2txt(input_image_control.value)
            #
            # TODO1: fix
            interrogate_control.click(fn=use_clip_for_prompt, inputs=[], outputs=[])
            
            #advanced_button.click(
            #    None,
            #    [],
            #    text,
            #    _js="""
            #    () => {
            #        const options = document.querySelector("body > gradio-app").querySelector("#advanced-options");
            #        options.style.display = ["none", ""].includes(options.style.display) ? "flex" : "none";
            #    }""",
            #)
            gr.HTML(
                """
                    <div class="footer">
                        <p>Model by <a href="https://huggingface.co/stabilityai" style="text-decoration: underline;" target="_blank">StabilityAI</a> - backend running JAX on TPUs due to generous support of <a href="https://sites.research.google/trc/about/" style="text-decoration: underline;" target="_blank">Google TRC program</a> - Gradio Demo by 🤗 Hugging Face
                        </p>
                    </div>
               """
            )
            with gr.Accordion(label="License", open=False):
                gr.HTML(
                    """<div class="acknowledgments">
                        <p><h4>LICENSE</h4>
    The model is licensed with a <a href="https://huggingface.co/stabilityai/stable-diffusion-2/blob/main/LICENSE-MODEL" style="text-decoration: underline;" target="_blank">CreativeML OpenRAIL++</a> license. The authors claim no rights on the outputs you generate, you are free to use them and are accountable for their use which must not go against the provisions set in this license. The license forbids you from sharing any content that violates any laws, produce any harm to a person, disseminate any personal information that would be meant for harm, spread misinformation and target vulnerable groups. For the full list of restrictions please <a href="https://huggingface.co/spaces/CompVis/stable-diffusion-license" target="_blank" style="text-decoration: underline;" target="_blank">read the license</a></p>
                        <p><h4>Biases and content acknowledgment</h4>
    Despite how impressive being able to turn text into image is, beware to the fact that this model may output content that reinforces or exacerbates societal biases, as well as realistic faces, pornography and violence. The model was trained on the <a href="https://laion.ai/blog/laion-5b/" style="text-decoration: underline;" target="_blank">LAION-5B dataset</a>, which scraped non-curated image-text-pairs from the internet (the exception being the removal of illegal content) and is meant for research purposes. You can read more in the <a href="https://huggingface.co/CompVis/stable-diffusion-v1-4" style="text-decoration: underline;" target="_blank">model card</a></p>
                   </div>
                    """
                )
                
    block.queue(concurrency_count=80, max_size=100).launch(max_threads=150)

                
#-------------------------------------------------------------------------------
# Runtime support

def main():
    """Entry point"""

    # Parse command line argument, show usage if --help given
    # TODO? auto_help=False
    main_app = Main(description=__doc__, skip_input=True,
                    boolean_options=[(BATCH_ARG, "Use batch mode--no UI"),
                                     (SERVER_ARG, "Run flask server"),
                                     (UI_ARG, "Show user interface"),
                                     ## TODO?: (TXT2IMG_ARG, "Run text-to-image"),
                                     (IMG2IMG_ARG, "Run image-to-image")],
                    text_options=[(PROMPT_ARG, "Positive prompt"),
                                  (NEGATIVE_ARG, "Negative prompt"),
                                  (IMAGE_ARG, "Filename for img2img input image")],
                    int_options=[(GUIDANCE_ARG, GUIDANCE_HELP)],
                    float_options=[(DENOISING_ARG, "Denoising factor for img2img")])
    debug.trace_object(5, main_app)
    debug.assertion(main_app.parsed_args)
    #
    batch_mode = main_app.get_parsed_option(BATCH_ARG)
    server_mode = main_app.get_parsed_option(SERVER_ARG)
    ui_mode = main_app.get_parsed_option(UI_ARG, not (batch_mode or server_mode))
    prompt = main_app.get_parsed_option(PROMPT_ARG, PROMPT)
    negative_prompt = main_app.get_parsed_option(NEGATIVE_ARG, NEGATIVE_PROMPT)
    guidance = main_app.get_parsed_option(GUIDANCE_ARG, GUIDANCE_SCALE)
    ## TODO?: use_txt2img = main_app.get_parsed_option(TXT2IMG_ARG, USE_TXT2IMG)
    use_img2img = main_app.get_parsed_option(IMG2IMG_ARG, USE_IMG2IMG)
    input_image_file = main_app.get_parsed_option(IMAGE_ARG)
    denoising_factor = main_app.get_parsed_option(DENOISING_ARG)
    ## TODO?: debug.assertion(use_txt2img ^ use_img2img)
    # TODO2: BASENAME and NUM_IMAGES
    ## TODO: x_mode = main_app.get_parsed_option(X_ARG)
    debug.assertion(not (batch_mode and server_mode))

    # Invoke UI via HTTP unless in batch mode
    global sd_instance
    sd_instance = StableDiffusion(use_hf_api=server_mode)
    if batch_mode:
        # Optionally convert input image into base64
        b64_image_encoding = (encode_image_file(input_image_file) if use_img2img else None)

        # Run generation
        images = (infer(prompt, negative_prompt, guidance, skip_img_spec=True) if (not use_img2img)
                  else infer_img2img(b64_image_encoding, denoising_factor, prompt, negative_prompt, guidance, skip_img_spec=True))
        # Save result to disk
        for i, image_encoding in enumerate(images):
            write_image_file(f"{BASENAME}-{i + 1}.png", image_encoding)
        # TODO2: get list of files via infer()
        file_spec = " ".join(gh.get_matching_files(f"{BASENAME}*png"))  
        print(f"See {file_spec} for output image(s).")
    # Start restful server
    elif server_mode:
        debug.assertion(SD_URL)
        debug.assertion(not sd_instance.server_url)
        debug.trace_object(5, flask_app)
        flask_app.run(host=SD_URL, port=SD_PORT, debug=SD_DEBUG)
    # Start UI
    else:
        debug.assertion(ui_mode)
        run_ui(use_img2img=use_img2img)


if __name__ == '__main__':
    debug.trace_current_context(level=TL.QUITE_DETAILED)
    main()
