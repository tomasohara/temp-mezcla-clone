#! /usr/bin/env python
#
# Test(s) for Hugging Face (HF) Stable Diffulion (SD) module: ../hf_stable_diffusion.py
#
# Notes:
# - This can be run as follows:
#   $ PYTHONPATH=".:$PYTHONPATH" python ./mezcla/tests/test_hf_stable_diffusion.py
#
# TODO3: check image attributes (e.g., backgfround color) and work in image classification (e.g., box)
#

"""Tests for hf_stable_diffusion module"""

# Standard packages
## OLD: import base64

# Installed packages
import numpy as np
import pytest
try:
    import diffusers
except:
    diffusers = None
try:
    import extcolors
except:
    extcolors = None
import PIL
import torch

# Local packages
from mezcla.unittest_wrapper import TestWrapper, trap_exception
from mezcla import debug
from mezcla import system
from mezcla import glue_helpers as gh
from mezcla.misc_utils import RANDOM_SEED
from mezcla.my_regex import my_re

# Note: Two references are used for the module to be tested:
#    THE_MODULE:                  global module object
#    TestTemplate.script_module:  path to file
import mezcla.examples.hf_stable_diffusion as THE_MODULE
hfsd = THE_MODULE

# Constants
TORCH_SEED = system.getenv_int("TORCH_SEED", RANDOM_SEED,
                               "Random seed for torch if non-zero")
NUMPY_SEED = system.getenv_int("NUMPY_SEED", RANDOM_SEED,
                               "Random seed for numpy if non-zero")

class TestIt(TestWrapper):
    """Class for testcase definition"""
    script_module = TestWrapper.get_testing_module_name(__file__, THE_MODULE)
    use_temp_base_dir = True            # treat TEMP_BASE as directory
    # note: temp_file defined by parent (along with script_module, temp_base, and test_num)

    @classmethod
    def setUpClass(cls):
        """One-time initialization (i.e., for entire class)"""
        debug.trace(5, f"TestIt.setUpClass(); cls={cls}")
        # note: should do parent processing first
        super().setUpClass()

        # Initialize torch's seed and numpy (n.b., separate from python, which misc_utils handles).
        # See https://pytorch.org/docs/stable/notes/randomness.html
        if TORCH_SEED:
            torch.manual_seed(TORCH_SEED)
        if NUMPY_SEED:
            np.random.seed(NUMPY_SEED)
        return

    def check_images(self, image_specs, label=None):
        """Make sure each of the IMAGE_SPECS are valid and return PIL image"""
        debug.trace(4, f"check_images({gh.elide(image_specs)}, {label})")
        label_spec = ("" if label is None else f"-{label}")
        images = []
        for i, spec in enumerate(image_specs):
            image = None
            try:
                # Make sure valid image
                image_bytes = hfsd.decode_base64_image(spec)
                image = hfsd.create_image(image_bytes)
                self.do_assert(isinstance(image, PIL.Image.Image))
            except:
                self.do_assert(False, "Problem decoding image spec")
            if image:
                images.append(image)
            # Save to disk if debugging
            if debug.debugging():
                temp_image_file = f"{self.temp_file}{label_spec}-{i + 1}.png"
                debug.trace_expr(4, temp_image_file)
                hfsd.write_image_file(temp_image_file, spec)
        return images

    
    @pytest.mark.skipif(not diffusers, reason="SD diffusers package missing")
    def test_01_simple_generation(self):
        """Makes sure simple image generation (txt2img) works as expected"""
        debug.trace(4, f"TestIt.test_01_simple_generation(); self={self}")
        
        # Run script to generate orange ball and get image filename.
        # ex: "See sd-app-image-1.png for output image(s)."
        script_output = self.run_script(
            options="--batch --prompt 'orange ball' --negative 'green blue red yellow purple pink brown'",
            env_options=f"BASENAME='{self.temp_base}' LOW_MEMORY=1", uses_stdin=True)
        debug.trace_expr(5, script_output)
        self.do_assert(my_re.search(r"See (\S+.png) for output image\(s\).", script_output.strip()))
        image_file = my_re.group(1)

        # Make sure expected dimension and  imagetype
        # ex: sd-app-image-3.png: PNG image data, 512 x 512, 8-bit/color RGB, non-interlaced
        file_info = gh.run(f"file {image_file}")
        debug.trace_expr(5, file_info)
        self.do_assert(my_re.search("PNG image data, 512 x 512, 8-bit/color RGB", file_info))
        # TODO2: orange in rgb-color profile for image
        # TODO3: clip interrogator mentions "ball"
        return

    ## TODO?
    ## #...............................................................................
    ##
    ## class TestIt2:
    ##    """Another class for testcase definition
    ##    Note: Needed to avoid error with pytest due to inheritance with unittest.TestCase via TestWrapper"""
    
    @pytest.mark.skipif(not diffusers, reason="SD diffusers package missing")
    def test_02_txt2img_pipeline(self):
        """Make sure valid SD pipeline created"""
        debug.trace(4, f"TestIt2.test_02_txt2img_pipeline(); self={self}")
        sd = THE_MODULE.StableDiffusion(use_hf_api=True)
        pipe = sd.init_pipeline()
        actual = my_re.split(r"\W+", str(pipe))
        expect = "CLIPImageProcessor CLIPTextModel StableDiffusionSafetyChecker text_encoder".split()
        debug.trace_expr(5, actual, expect, delim="\n")
        self.do_assert(len(system.intersection(actual, expect)) > 2)
        return
    
    @pytest.mark.xfail                   # TODO: remove xfail
    @pytest.mark.skipif(not diffusers, reason="SD diffusers package missing")
    def test_03_txt2img_generation(self):
        """Make sure text-to-image reasonable"""
        debug.trace(4, f"TestIt2.test_03_txt2img_generation(); self={self}")
        sd = THE_MODULE.StableDiffusion(use_hf_api=True)
        ## TODO: NUM_IMAGES = 2
        NUM_IMAGES = 1
        # note: generate image with high adherence guidance for prompt
        image_specs = sd.infer(prompt="cute puppy", negative_prompt="pitbull", scale=20, num_images=NUM_IMAGES, skip_img_spec=True)
        images = self.check_images(image_specs, label="txt2img")
        self.do_assert(len(images) == NUM_IMAGES)
        description = sd.infer_img2txt(image_b64=image_specs[0])
        self.do_assert(my_re.search(r"canine|dog|puppy", description))
        return

    @pytest.mark.xfail                   # TODO: remove xfail
    @pytest.mark.skipif(not diffusers, reason="SD diffusers package missing")
    @trap_exception
    def test_04_img2img_generation(self):
        """Make sure image-to-image reasonable"""
        debug.trace(4, f"TestIt2.test_04_img2img_generation(); self={self}")
        sd = THE_MODULE.StableDiffusion(use_hf_api=True)
        ## TODO: NUM_IMAGES = 2
        NUM_IMAGES = 1
        # TODO2: use larger image
        PACMAC_LIKE_IMAGE = gh.resolve_path("sd-spooky-pacman.png", heuristic=True)
        pacmac_like_base64 = THE_MODULE.encode_image_file(PACMAC_LIKE_IMAGE)
        # note: generate derived image with high fidelity to original and low adherence guidance to prompt
        image_specs = sd.infer_img2img(image_b64=pacmac_like_base64, denoise=0.25, prompt="cute puppy", negative_prompt="pitbull",
                                       scale=3.5, num_images=NUM_IMAGES, skip_img_spec=True)
        self.do_assert(len(image_specs) == NUM_IMAGES)
        ## BAD: self.do_assert(isinstance(images[0], PIL.Image.Image))
        # TODO1: image recognition doesn't yield dog
        images = self.check_images(image_specs, label="img2img")
        self.do_assert(len(images) == NUM_IMAGES)
        description = sd.infer_img2txt(image_b64=image_specs[0])
        self.do_assert(not my_re.search(r"canine|dog|puppy", description))
        return

    @pytest.mark.xfail                   # TODO: remove xfail
    @pytest.mark.skipif(not diffusers, reason="SD diffusers package missing")
    @trap_exception
    def test_05_img2txt_generation(self):
        """Make sure image-to-text reasonable"""
        debug.trace(4, f"TestIt2.test_05_img2txt_generation(); self={self}")
        # TODO2: use common setup method (e.g., via TestWrapper)
        sd = THE_MODULE.StableDiffusion(use_hf_api=True)
        PACMAC_LIKE_IMAGE = gh.resolve_path("sd-spooky-pacman.png", heuristic=True)
        pacmac_like_base64 = THE_MODULE.encode_image_file(PACMAC_LIKE_IMAGE)
        description = sd.infer_img2txt(image_b64=pacmac_like_base64)
        # TODO4: assert(english-like-text(description))
        self.do_assert(not my_re.search(r"canine|dog|puppy", description))
        return

    @pytest.mark.xfail                   # TODO: remove xfail
    @pytest.mark.skipif(not extcolors, reason="extcolors package missing")
    @trap_exception
    def test_06_prompted_color(self):
        """Make sure prompted color is used"""
        debug.trace(4, f"TestIt2.test_06_prompted_color(); self={self}")
        sd = THE_MODULE.StableDiffusion(use_hf_api=True, low_memory=True)
        images = sd.infer(prompt="a ripe orange", scale=30, skip_img_spec=True)
        # note: encodes image base-64 str data into bytes and then decodes into image bytes
        ## OLD: image_data = (base64.decodebytes(images[0].encode()))
        image_data = hfsd.decode_base64_image(images[0])
        image_path = gh.create_temp_file(image_data, binary=True)
        # note: use of rgb_color_name.py allows for fudge factor
        # $ extcolors sd-app-image-1.png | rgb_color_name.py - | grep orange
        # <(255, 92, 0), orangered>   :  47.07% (123388)
        # <(255, 153, 0), orange>  :   6.13% (16074)
        color_output = gh.run(f"extcolors '{image_path}' | rgb_color_name.py - 2> /dev/null")
        debug.trace_expr(4, color_output)
        self.do_assert("orange" in color_output)
        self.do_assert(len(images) == 1)
        return

#------------------------------------------------------------------------

if __name__ == '__main__':
    debug.trace_current_context()
    pytest.main([__file__])
