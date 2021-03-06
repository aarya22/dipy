from __future__ import division, print_function, absolute_import

import logging
import numpy as np
import os.path
from ast import literal_eval

import nibabel as nib

from dipy.core.gradients import gradient_table
from dipy.data import get_sphere
from dipy.io.gradients import read_bvals_bvecs
from dipy.io.peaks import save_peaks, peaks_to_niftis
from dipy.reconst.csdeconv import (ConstrainedSphericalDeconvModel,
                                   auto_response)
from dipy.reconst.dti import (TensorModel, color_fa, fractional_anisotropy,
                              geodesic_anisotropy, mean_diffusivity,
                              axial_diffusivity, radial_diffusivity,
                              lower_triangular, mode as get_mode)
from dipy.reconst.peaks import peaks_from_model
from dipy.reconst.shm import CsaOdfModel
from dipy.workflows.workflow import Workflow

from dipy.reconst import mapmri

class ReconstMAPMRIFlow(Workflow):
    @classmethod
    def get_short_name(cls):
        return 'mapmri'

    def run(self, data_file, data_bvecs, data_bvals, model_type, out_rtop='rtop.nii.gz', out_lapnorm='lapnorm.nii.gz',
            out_msd='msd.nii.gz', out_qiv='qiv.nii.gz', out_rtap='rtap.nii.gz', out_rtpp='rtpp.nii.gz',
            small_delta=0.0129, big_delta=0.0218, save_metrics=[], out_dir=''):
        """ Workflow for the app-dipy-mapmri on Brain-Life (www.brain-life.org). 
        Generates RTOP ??? saved in a ??? format in input files provided by
        `data_file` and saves the png file to an output directory specified by 
        `out_dir`.

        Parameters
        ----------
        data_file : string
            Path to the input volume.
        data_bvecs : string
            Path to the bvec files.
        data_bvals : 
            Path to the bval files.
        small_delta :
            Small delta value used in generation of gradient table of provided
            bval and bvec. (default: 0.0129)
        big_delta :
            Big delta value used in generation of gradient table of provided 
            bval and bvec. (default: 0.0218)
        model_type : string
            Model type to fit.
            Possible values: laplacian, positivity, both
            (default: both)
        save_metrics :
            List of metrics to save.
            Possible values: rtop, laplacian_signal, msd, qiv, rtap, rtpp
            (default: [] (all))
        out_dir : string, optional
            Output directory (default: input file directory)
        out_rtop : string, optional
            Name of the rtop to be saved
        out_lapnorm : string, optional
            Name of the norm of laplacian signal to be saved
        out_msd : string, optional
            Name of the msd to be saved
        out_qiv : string, optional
            Name of the qiv to be saved
        out_rtap : string, optional
            Name of the rtap to be saved
        out_rtpp : string, optional
            Name of the rtpp to be saved
        """
        io_it = self.get_io_iterator()
        for dwi, bval, bvec, out_rtop, out_lapnorm, out_msd, out_qiv, out_rtap, out_rtpp in io_it:

            logging.info('Computing DTI metrics for {0}'.format(dwi))
            img = nib.load(dwi)
            data = img.get_data()
            affine = img.affine
            bvals, bvecs = read_bvals_bvecs(bval, bvec)

            gtab = gradient_table(bvals=bvals, bvecs=bvecs,
                                  small_delta=small_delta,
                                  big_delta=big_delta, b0_threshold=50)

            # For testing purposes, will change later
            data_small = data[60:85, 80:81, 60:85]
            
            if not model_type:
                model_type = 'both'

            if not save_metrics:
                save_metrics = ['rtop', 'laplacian_signal', 'msd', 'qiv', 'rtap', 'rtpp']

            # print('data.shape (%d, %d, %d, %d)' % data.shape)

            radial_order = 6
            
            # How do I save the rtop in a useful form? A picture? A numpy array?
            # Save them as nifti image

            if model_type is 'laplacian':
                map_model_aniso = mapmri.MapmriModel(gtab, radial_order=radial_order,
                                                     laplacian_regularization=True,
                                                     laplacian_weighting=.2)
                mapfit_aniso = map_model_aniso.fit(data_small)

            elif model_type is 'positivity':

                map_model_aniso = mapmri.MapmriModel(gtab, radial_order=radial_order,
                                                     laplacian_regularization=False,
                                                     positivity_constraint=True)
                mapfit_aniso = map_model_aniso.fit(data_small)

            elif model_type is 'both':
                map_model_aniso = mapmri.MapmriModel(gtab, radial_order=radial_order,
                                                     laplacian_regularization=True,
                                                     laplacian_weighting=.05,
                                                     positivity_constraint=True)
                mapfit_aniso = map_model_aniso.fit(data_small)

            # Not sure where to get affine or metadata?
            if 'rtop' in save_metrics:
                r = mapfit_aniso.rtop()
                print(type(r))
                rtop = nib.nifti1.Nifti1Image(r.astype(np.float32), affine)
                nib.save(rtop, out_rtop)

            if 'laplacian_signal' in save_metrics:
                l = mapfit_aniso.norm_of_laplacian_signal()
                print(type(l))
                lap = nib.nifti1.Nifti1Image(l.astype(np.float32), affine)
                nib.save(lap, out_lapnorm)

            if 'msd' in save_metrics:
                m = mapfit_aniso.msd()
                print(type(m))
                msd = nib.nifti1.Nifti1Image(m.astype(np.float32), affine)
                nib.save(msd, out_msd)

            if 'qiv' in save_metrics:
                q = mapfit_aniso.qiv()
                print(type(q))
                qiv = nib.nifti1.Nifti1Image(q.astype(np.float32), affine)
                nib.save(qiv, out_qiv)

            if 'rtap' in save_metrics:
                r = mapfit_aniso.rtap()
                print(type(r))
                rtap = nib.nifti1.Nifti1Image(r.astype(np.float32), affine)
                nib.save(rtap, out_rtap)

            if 'rtpp' in save_metrics:
                r = mapfit_aniso.rtpp()
                print(type(r))
                rtpp = nib.nifti1.Nifti1Image(r.astype(np.float32), affine)
                nib.save(rtpp, out_rtpp)

            logging.info('MAPMRI saved in {0}'.
                         format(os.path.dirname(out_rtpp)))
            

class ReconstMAPMRILaplacian(ReconstMAPMRIFlow):
    @classmethod
    def get_short_name(cls):
        return "mmri_laplacian"

    def run(self, data_file, data_bvecs, data_bvals, out_rtop='lap_rtop.nii.gz', out_lapnorm='lap_lapnorm.nii.gz',
            out_msd='lap_msd.nii.gz', out_qiv='lap_qiv.nii.gz', out_rtap='lap_rtap.nii.gz', out_rtpp='lap_rtpp.nii.gz',
            model_type='laplacian', small_delta=0.0129, big_delta=0.0218, save_metrics=[], out_dir=''):
        """ Workflow for the app-dipy-mapmri on Brain-Life (www.brain-life.org).
            Generates rtop, lapnorm, msd, qiv, rtap, rtpp for a laplacian mapmri saved in a nifti format in input files
            provided by `data_file` and saves the nifti files to an output directory specified by
            `out_dir`.

            Parameters
            ----------
            data_file : string
                Path to the input volume.
            data_bvecs : string
                Path to the bvec files.
            data_bvals :
                Path to the bval files.
            small_delta :
                Small delta value used in generation of gradient table of provided
                bval and bvec. (default: 0.0129)
            big_delta :
                Big delta value used in generation of gradient table of provided
                bval and bvec. (default: 0.0218)
            model_type : string
                Model type to fit.
                Possible values: laplacian, positivity, both
                (default: laplacian)
            save_metrics :
                List of metrics to save.
                Possible values: rtop, laplacian_signal, msd, qiv, rtap, rtpp
                (default: [] (all))
            out_dir : string, optional
                Output directory (default: input file directory)
            out_rtop : string, optional
                Name of the rtop to be saved
                (default: lap_rtop)
            out_lapnorm : string, optional
                Name of the norm of laplacian signal to be saved
                (default: lap_lapnorm)
            out_msd : string, optional
                Name of the msd to be saved
                (default: lap_msd)
            out_qiv : string, optional
                Name of the qiv to be saved
                (default: lap_qiv)
            out_rtap : string, optional
                Name of the rtap to be saved
                (default: lap_rtap)
            out_rtpp : string, optional
                Name of the rtpp to be saved
                (default: lap_rtpp)
            """
        
        super(ReconstMAPMRILaplacian, self). \
            run(data_file, data_bvecs, data_bvals, out_rtop, out_lapnorm, out_msd, out_qiv,
                out_rtap, out_rtpp, model_type, small_delta, big_delta, save_metrics, out_dir)


class ReconstMAPMRIPositivity(ReconstMAPMRIFlow):
    @classmethod
    def get_short_name(cls):
        return "mmri_positivity"

    def run(self, data_file, data_bvecs, data_bvals, out_rtop='pos_rtop.nii.gz', out_lapnorm='pos_lapnorm.nii.gz',
            out_msd='pos_msd.nii.gz', out_qiv='pos_qiv.nii.gz', out_rtap='pos_rtap.nii.gz', out_rtpp='pos_rtpp.nii.gz',
            model_type='positivity', small_delta=0.0129, big_delta=0.0218, save_metrics=[], out_dir=''):
        """ Workflow for the app-dipy-mapmri on Brain-Life (www.brain-life.org).
            Generates rtop, lapnorm, msd, qiv, rtap, rtpp for a positivity mapmri saved
            in a nifti format in input files provided by `data_file` and saves the nifti files
            to an output directory specified by `out_dir`.

            Parameters
            ----------
            data_file : string
                Path to the input volume.
            data_bvecs : string
                Path to the bvec files.
            data_bvals :
                Path to the bval files.
            small_delta :
                Small delta value used in generation of gradient table of provided
                bval and bvec. (default: 0.0129)
            big_delta :
                Big delta value used in generation of gradient table of provided
                bval and bvec. (default: 0.0218)
            model_type : string
                Model type to fit.
                Possible values: laplacian, positivity, both
                (default: laplacian)
            save_metrics :
                List of metrics to save.
                Possible values: rtop, laplacian_signal, msd, qiv, rtap, rtpp
                (default: [] (all))
            out_dir : string, optional
                Output directory (default: input file directory)
            out_rtop : string, optional
                Name of the rtop to be saved
                (default: pos_rtop)
            out_lapnorm : string, optional
                Name of the norm of laplacian signal to be saved
                (default: pos_lapnorm)
            out_msd : string, optional
                Name of the msd to be saved
                (default: pos_msd)
            out_qiv : string, optional
                Name of the qiv to be saved
                (default: pos_qiv)
            out_rtap : string, optional
                Name of the rtap to be saved
                (default: pos_rtap)
            out_rtpp : string, optional
                Name of the rtpp to be saved
                (default: pos_rtpp)
            """

        super(ReconstMAPMRIPositivity, self). \
            run(data_file, data_bvecs, data_bvals, out_rtop, out_lapnorm, out_msd, out_qiv,
                out_rtap, out_rtpp, model_type, small_delta, big_delta, save_metrics, out_dir)
        

class ReconstMAPMRIBoth(ReconstMAPMRIFlow):
    @classmethod
    def get_short_name(cls):
        return "mmri_both"

    def run(self, data_file, data_bvecs, data_bvals, out_rtop='both_rtop.nii.gz', out_lapnorm='both_lapnorm.nii.gz',
            out_msd='both_msd.nii.gz', out_qiv='both_qiv.nii.gz', out_rtap='both_rtap.nii.gz',
            out_rtpp='both_rtpp.nii.gz', model_type='both', small_delta=0.0129, big_delta=0.0218, save_metrics=[],
            out_dir=''):
        """ Workflow for the app-dipy-mapmri on Brain-Life (www.brain-life.org).
            Generates rtop, lapnorm, msd, qiv, rtap, rtpp for a laplacian mapmri
            saved in a nifti format in input files provided by `data_file`
            and saves the nifti files to an output directory specified by `out_dir`.

            Parameters
            ----------
            data_file : string
                Path to the input volume.
            data_bvecs : string
                Path to the bvec files.
            data_bvals :
                Path to the bval files.
            small_delta :
                Small delta value used in generation of gradient table of provided
                bval and bvec. (default: 0.0129)
            big_delta :
                Big delta value used in generation of gradient table of provided
                bval and bvec. (default: 0.0218)
            model_type : string
                Model type to fit.
                Possible values: laplacian, positivity, both
                (default: laplacian)
            save_metrics :
                List of metrics to save.
                Possible values: rtop, laplacian_signal, msd, qiv, rtap, rtpp
                (default: [] (all))
            out_dir : string, optional
                Output directory (default: input file directory)
            out_rtop : string, optional
                Name of the rtop to be saved
                (default: both_rtop)
            out_lapnorm : string, optional
                Name of the norm of bothlacian signal to be saved
                (default: both_lapnorm)
            out_msd : string, optional
                Name of the msd to be saved
                (default: both_msd)
            out_qiv : string, optional
                Name of the qiv to be saved
                (default: both_qiv)
            out_rtap : string, optional
                Name of the rtap to be saved
                (default: both_rtap)
            out_rtpp : string, optional
                Name of the rtpp to be saved
                (default: both_rtpp)
            """

        super(ReconstMAPMRIBoth, self). \
            run(data_file, data_bvecs, data_bvals, out_rtop, out_lapnorm, out_msd, out_qiv,
                out_rtap, out_rtpp, model_type, small_delta, big_delta, save_metrics, out_dir)

class ReconstDtiFlow(Workflow):
    @classmethod
    def get_short_name(cls):
        return 'dti'

    def run(self, input_files, bvalues, bvectors, mask_files, b0_threshold=0.0,
            save_metrics=[],
            out_dir='', out_tensor='tensors.nii.gz', out_fa='fa.nii.gz',
            out_ga='ga.nii.gz', out_rgb='rgb.nii.gz', out_md='md.nii.gz',
            out_ad='ad.nii.gz', out_rd='rd.nii.gz', out_mode='mode.nii.gz',
            out_evec='evecs.nii.gz', out_eval='evals.nii.gz'):
        """ Workflow for tensor reconstruction and for computing DTI metrics.
        Performs a tensor reconstruction on the files by 'globing'
        ``input_files`` and saves the DTI metrics in a directory specified by
        ``out_dir``.

        Parameters
        ----------
        input_files : string
            Path to the input volumes. This path may contain wildcards to
            process multiple inputs at once.
        bvalues : string
            Path to the bvalues files. This path may contain wildcards to use
            multiple bvalues files at once.
        bvectors : string
            Path to the bvectors files. This path may contain wildcards to use
            multiple bvectors files at once.
        mask_files : string
            Path to the input masks. This path may contain wildcards to use
            multiple masks at once. (default: No mask used)
        b0_threshold : float, optional
            Threshold used to find b=0 directions (default 0.0)
        save_metrics : variable string, optional
            List of metrics to save.
            Possible values: fa, ga, rgb, md, ad, rd, mode, tensor, evec, eval
            (default [] (all))
        out_dir : string, optional
            Output directory (default input file directory)
        out_tensor : string, optional
            Name of the tensors volume to be saved (default 'tensors.nii.gz')
        out_fa : string, optional
            Name of the fractional anisotropy volume to be saved
            (default 'fa.nii.gz')
        out_ga : string, optional
            Name of the geodesic anisotropy volume to be saved
            (default 'ga.nii.gz')
        out_rgb : string, optional
            Name of the color fa volume to be saved (default 'rgb.nii.gz')
        out_md : string, optional
            Name of the mean diffusivity volume to be saved
            (default 'md.nii.gz')
        out_ad : string, optional
            Name of the axial diffusivity volume to be saved
            (default 'ad.nii.gz')
        out_rd : string, optional
            Name of the radial diffusivity volume to be saved
            (default 'rd.nii.gz')
        out_mode : string, optional
            Name of the mode volume to be saved (default 'mode.nii.gz')
        out_evec : string, optional
            Name of the eigenvectors volume to be saved
            (default 'evecs.nii.gz')
        out_eval : string, optional
            Name of the eigenvalues to be saved (default 'evals.nii.gz')
        """
        io_it = self.get_io_iterator()

        for dwi, bval, bvec, mask, otensor, ofa, oga, orgb, omd, oad, orad, \
            omode, oevecs, oevals in io_it:

            logging.info('Computing DTI metrics for {0}'.format(dwi))
            img = nib.load(dwi)
            data = img.get_data()
            affine = img.affine

            if mask is None:
                mask = None
            else:
                mask = nib.load(mask).get_data().astype(np.bool)

            tenfit, _ = self.get_fitted_tensor(data, mask, bval, bvec,
                                               b0_threshold)

            if not save_metrics:
                save_metrics = ['fa', 'md', 'rd', 'ad', 'ga', 'rgb', 'mode',
                                'evec', 'eval', 'tensor']

            FA = fractional_anisotropy(tenfit.evals)
            FA[np.isnan(FA)] = 0
            FA = np.clip(FA, 0, 1)

            if 'tensor' in save_metrics:
                tensor_vals = lower_triangular(tenfit.quadratic_form)
                correct_order = [0, 1, 3, 2, 4, 5]
                tensor_vals_reordered = tensor_vals[..., correct_order]
                fiber_tensors = nib.Nifti1Image(tensor_vals_reordered.astype(
                    np.float32), affine)
                nib.save(fiber_tensors, otensor)

            if 'fa' in save_metrics:
                fa_img = nib.Nifti1Image(FA.astype(np.float32), affine)
                nib.save(fa_img, ofa)

            if 'ga' in save_metrics:
                GA = geodesic_anisotropy(tenfit.evals)
                ga_img = nib.Nifti1Image(GA.astype(np.float32), affine)
                nib.save(ga_img, oga)

            if 'rgb' in save_metrics:
                RGB = color_fa(FA, tenfit.evecs)
                rgb_img = nib.Nifti1Image(np.array(255 * RGB, 'uint8'), affine)
                nib.save(rgb_img, orgb)

            if 'md' in save_metrics:
                MD = mean_diffusivity(tenfit.evals)
                md_img = nib.Nifti1Image(MD.astype(np.float32), affine)
                nib.save(md_img, omd)

            if 'ad' in save_metrics:
                AD = axial_diffusivity(tenfit.evals)
                ad_img = nib.Nifti1Image(AD.astype(np.float32), affine)
                nib.save(ad_img, oad)

            if 'rd' in save_metrics:
                RD = radial_diffusivity(tenfit.evals)
                rd_img = nib.Nifti1Image(RD.astype(np.float32), affine)
                nib.save(rd_img, orad)

            if 'mode' in save_metrics:
                MODE = get_mode(tenfit.quadratic_form)
                mode_img = nib.Nifti1Image(MODE.astype(np.float32), affine)
                nib.save(mode_img, omode)

            if 'evec' in save_metrics:
                evecs_img = nib.Nifti1Image(tenfit.evecs.astype(np.float32), affine)
                nib.save(evecs_img, oevecs)

            if 'eval' in save_metrics:
                evals_img = nib.Nifti1Image(tenfit.evals.astype(np.float32), affine)
                nib.save(evals_img, oevals)

            logging.info('DTI metrics saved in {0}'.
                         format(os.path.dirname(oevals)))

    def get_tensor_model(self, gtab):
        return TensorModel(gtab, fit_method="WLS")

    def get_fitted_tensor(self, data, mask, bval, bvec, b0_threshold=0):

        logging.info('Tensor estimation...')
        bvals, bvecs = read_bvals_bvecs(bval, bvec)
        gtab = gradient_table(bvals, bvecs, b0_threshold=b0_threshold)

        tenmodel = self.get_tensor_model(gtab)
        tenfit = tenmodel.fit(data, mask)

        return tenfit, gtab


class ReconstDtiRestoreFlow(ReconstDtiFlow):
    @classmethod
    def get_short_name(cls):
        return 'dti_restore'

    def run(self, input_files, bvalues, bvectors, mask_files, sigma,
            b0_threshold=0.0, save_metrics=[], jacobian=True,
            out_dir='', out_tensor='tensors.nii.gz', out_fa='fa.nii.gz',
            out_ga='ga.nii.gz', out_rgb='rgb.nii.gz', out_md='md.nii.gz',
            out_ad='ad.nii.gz', out_rd='rd.nii.gz', out_mode='mode.nii.gz',
            out_evec='evecs.nii.gz', out_eval='evals.nii.gz'):
        """ Workflow for tensor reconstruction and for computing DTI metrics.
            Performs a tensor reconstruction on the files by 'globing'
            ``input_files`` and saves the DTI metrics in a directory specified by
            ``out_dir``.

            Parameters
            ----------
            input_files : string
                Path to the input volumes. This path may contain wildcards to
                process multiple inputs at once.
            bvalues : string
                Path to the bvalues files. This path may contain wildcards to use
                multiple bvalues files at once.
            bvectors : string
                Path to the bvectors files. This path may contain wildcards to use
                multiple bvectors files at once.
            mask_files : string
                Path to the input masks. This path may contain wildcards to use
                multiple masks at once. (default: No mask used)
            sigma : float
                An estimate of the variance.
            b0_threshold : float, optional
                Threshold used to find b=0 directions (default 0.0)
            save_metrics : variable string, optional
                List of metrics to save.
                Possible values: fa, ga, rgb, md, ad, rd, mode, tensor, evec, eval
                (default [] (all))
            jacobian : bool, optional
                Whether to use the Jacobian of the tensor to speed the
                non-linear optimization procedure used to fit the tensor
                parameters (default True)
            out_dir : string, optional
                Output directory (default input file directory)
            out_tensor : string, optional
                Name of the tensors volume to be saved (default 'tensors.nii.gz')
            out_fa : string, optional
                Name of the fractional anisotropy volume to be saved
                (default 'fa.nii.gz')
            out_ga : string, optional
                Name of the geodesic anisotropy volume to be saved
                (default 'ga.nii.gz')
            out_rgb : string, optional
                Name of the color fa volume to be saved (default 'rgb.nii.gz')
            out_md : string, optional
                Name of the mean diffusivity volume to be saved
                (default 'md.nii.gz')
            out_ad : string, optional
                Name of the axial diffusivity volume to be saved
                (default 'ad.nii.gz')
            out_rd : string, optional
                Name of the radial diffusivity volume to be saved
                (default 'rd.nii.gz')
            out_mode : string, optional
                Name of the mode volume to be saved (default 'mode.nii.gz')
            out_evec : string, optional
                Name of the eigenvectors volume to be saved
                (default 'evecs.nii.gz')
            out_eval : string, optional
                Name of the eigenvalues to be saved (default 'evals.nii.gz')
            """
        self.sigma = sigma
        self.jacobian = jacobian

        super(ReconstDtiRestoreFlow, self). \
            run(input_files, bvalues, bvectors, mask_files, b0_threshold,
                save_metrics, out_dir, out_tensor, out_fa, out_ga, out_rgb,
                out_md, out_ad, out_rd, out_mode, out_evec, out_eval)


class ReconstCSDFlow(Workflow):
    @classmethod
    def get_short_name(cls):
        return 'csd'

    def run(self, input_files, bvalues, bvectors, mask_files,
            b0_threshold=0.0,
            frf=[15.0, 4.0, 4.0], extract_pam_values=False, out_dir='',
            out_pam='peaks.pam5', out_shm='shm.nii.gz',
            out_peaks_dir='peaks_dirs.nii.gz',
            out_peaks_values='peaks_values.nii.gz',
            out_peaks_indices='peaks_indices.nii.gz', out_gfa='gfa.nii.gz'):
        """ Workflow for peaks computation. Peaks computation is done by 'globing'
            ``input_files`` and saves the peaks in a directory specified by
            ``out_dir``.

        Parameters
        ----------
        input_files : string
            Path to the input volumes. This path may contain wildcards to
            process multiple inputs at once.
        bvalues : string
            Path to the bvalues files. This path may contain wildcards to use
            multiple bvalues files at once.
        bvectors : string
            Path to the bvectors files. This path may contain wildcards to use
            multiple bvectors files at once.
        mask_files : string
            Path to the input masks. This path may contain wildcards to use
            multiple masks at once. (default: No mask used)
        b0_threshold : float, optional
            Threshold used to find b=0 directions
        frf : tuple, optional
            Fiber response function to me mutiplied by 10**-4 (default: 15,4,4)
        extract_pam_values : bool, optional
            Wheter or not to save pam volumes as single nifti files.
        out_dir : string, optional
            Output directory (default input file directory)
        out_pam : string, optional
            Name of the peaks volume to be saved (default 'peaks.pam5')
        out_shm : string, optional
            Name of the shperical harmonics volume to be saved
            (default 'shm.nii.gz')
        out_peaks_dir : string, optional
            Name of the peaks directions volume to be saved
            (default 'peaks_dirs.nii.gz')
        out_peaks_values : string, optional
            Name of the peaks values volume to be saved
            (default 'peaks_values.nii.gz')
        out_peaks_indices : string, optional
            Name of the peaks indices volume to be saved
            (default 'peaks_indices.nii.gz')
        out_gfa : string, optional
            Name of the generalise fa volume to be saved (default 'gfa.nii.gz')
        """
        io_it = self.get_io_iterator()

        for dwi, bval, bvec, maskfile, opam, oshm, opeaks_dir, opeaks_values, \
            opeaks_indices, ogfa in io_it:

            logging.info('Computing fiber odfs for {0}'.format(dwi))
            vol = nib.load(dwi)
            data = vol.get_data()
            affine = vol.get_affine()

            bvals, bvecs = read_bvals_bvecs(bval, bvec)
            gtab = gradient_table(bvals, bvecs, b0_threshold=b0_threshold)
            mask_vol = nib.load(maskfile).get_data().astype(np.bool)

            sh_order = 8
            if data.shape[-1] < 15:
                raise ValueError(
                    'You need at least 15 unique DWI volumes to '
                    'compute fiber odfs. You currently have: {0}'
                    ' DWI volumes.'.format(data.shape[-1]))
            elif data.shape[-1] < 30:
                sh_order = 6

            response, ratio = auto_response(gtab, data)
            response = list(response)

            if frf is not None:
                if isinstance(frf, str):
                    l01 = np.array(literal_eval(frf), dtype=np.float64)
                else:
                    l01 = np.array(frf)

                l01 *= 10 ** -4
                response[0] = np.array([l01[0], l01[1], l01[1]])
                ratio = l01[1] / l01[0]

            logging.info(
                'Eigenvalues for the frf of the input data are :{0}'
                    .format(response[0]))
            logging.info('Ratio for smallest to largest eigen value is {0}'
                         .format(ratio))

            peaks_sphere = get_sphere('symmetric362')

            csd_model = ConstrainedSphericalDeconvModel(gtab, response,
                                                        sh_order=sh_order)

            peaks_csd = peaks_from_model(model=csd_model,
                                         data=data,
                                         sphere=peaks_sphere,
                                         relative_peak_threshold=.5,
                                         min_separation_angle=25,
                                         mask=mask_vol,
                                         return_sh=True,
                                         sh_order=sh_order,
                                         normalize_peaks=True,
                                         parallel=False)
            peaks_csd.affine = affine

            save_peaks(opam, peaks_csd)

            if extract_pam_values:
                peaks_to_niftis(peaks_csd, oshm, opeaks_dir, opeaks_values,
                                opeaks_indices, ogfa, reshape_dirs=True)

            logging.info('Peaks saved in {0}'.format(os.path.dirname(opam)))

            return io_it


class ReconstCSAFlow(Workflow):
    @classmethod
    def get_short_name(cls):
        return 'csa'

    def run(self, input_files, bvalues, bvectors, mask_files,
            b0_threshold=0.0, extract_pam_values=False, out_dir='',
            out_pam='peaks.pam5', out_shm='shm.nii.gz',
            out_peaks_dir='peaks_dirs.nii.gz',
            out_peaks_values='peaks_values.nii.gz',
            out_peaks_indices='peaks_indices.nii.gz',
            out_gfa='gfa.nii.gz'):
        """ Workflow for peaks computation. Peaks computation is done by 'globing'
            ``input_files`` and saves the peaks in a directory specified by
            ``out_dir``.

        Parameters
        ----------
        input_files : string
            Path to the input volumes. This path may contain wildcards to
            process multiple inputs at once.
        bvalues : string
            Path to the bvalues files. This path may contain wildcards to use
            multiple bvalues files at once.
        bvectors : string
            Path to the bvectors files. This path may contain wildcards to use
            multiple bvectors files at once.
        mask_files : string
            Path to the input masks. This path may contain wildcards to use
            multiple masks at once. (default: No mask used)
        b0_threshold : float, optional
            Threshold used to find b=0 directions
        extract_pam_values : bool, optional
            Wheter or not to save pam volumes as single nifti files.
        out_dir : string, optional
            Output directory (default input file directory)
        out_pam : string, optional
            Name of the peaks volume to be saved (default 'peaks.pam5')
        out_shm : string, optional
            Name of the shperical harmonics volume to be saved
            (default 'shm.nii.gz')
        out_peaks_dir : string, optional
            Name of the peaks directions volume to be saved
            (default 'peaks_dirs.nii.gz')
        out_peaks_values : string, optional
            Name of the peaks values volume to be saved
            (default 'peaks_values.nii.gz')
        out_peaks_indices : string, optional
            Name of the peaks indices volume to be saved
            (default 'peaks_indices.nii.gz')
        out_gfa : string, optional
            Name of the generalise fa volume to be saved (default 'gfa.nii.gz')
        """
        io_it = self.get_io_iterator()

        for dwi, bval, bvec, maskfile, opam, oshm, opeaks_dir, \
            opeaks_values, opeaks_indices, ogfa in io_it:

            logging.info('Computing fiber odfs for {0}'.format(dwi))
            vol = nib.load(dwi)
            data = vol.get_data()
            affine = vol.get_affine()

            bvals, bvecs = read_bvals_bvecs(bval, bvec)
            gtab = gradient_table(bvals, bvecs,
                                  b0_threshold=b0_threshold)
            mask_vol = nib.load(maskfile).get_data().astype(np.bool)

            sh_order = 8
            if data.shape[-1] < 15:
                raise ValueError(
                    'You need at least 15 unique DWI volumes to '
                    'compute fiber odfs. You currently have: {0}'
                    ' DWI volumes.'.format(data.shape[-1]))
            elif data.shape[-1] < 30:
                sh_order = 6

            response, ratio = auto_response(gtab, data)
            response = list(response)

            logging.info(
                'Eigenvalues for the frf of the input data are :{0}'
                    .format(response[0]))
            logging.info(
                'Ratio for smallest to largest eigen value is {0}'
                    .format(ratio))

            peaks_sphere = get_sphere('symmetric362')

            csa_model = CsaOdfModel(gtab, sh_order)

            peaks_csa = peaks_from_model(model=csa_model,
                                         data=data,
                                         sphere=peaks_sphere,
                                         relative_peak_threshold=.5,
                                         min_separation_angle=25,
                                         mask=mask_vol,
                                         return_sh=True,
                                         sh_order=sh_order,
                                         normalize_peaks=True,
                                         parallel=False)
            peaks_csa.affine = affine

            save_peaks(opam, peaks_csa)

            if extract_pam_values:
                peaks_to_niftis(peaks_csa, oshm, opeaks_dir,
                                opeaks_values,
                                opeaks_indices, ogfa, reshape_dirs=True)

            logging.info(
                'Peaks saved in {0}'.format(os.path.dirname(opam)))

            return io_it

    def get_tensor_model(self, gtab):
        return TensorModel(gtab, fit_method="RT", sigma=self.sigma,
                           jac=self.jacobian)
