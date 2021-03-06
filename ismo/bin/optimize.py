#!/bin/env python

import json
import ismo.optimizers
import ismo.objective_function
import tensorflow.keras.models
import os.path
import pickle

if __name__ == '__main__':
    import argparse

    import numpy as np

    parser = argparse.ArgumentParser(description="""
Optimizes the parameters as starting values under the given neural network and objective function

It assumes the parameter file is of the form
parameter_sample_0
parameter_sample_1

""")

    parser.add_argument('--input_model_files', type=str, required=True, nargs='+',
                        help='Input filename for models (full path, hdf5 file)')

    parser.add_argument('--objective_python_module', type=str, required=True,
                        help='Input filename for for the objective function (python module, full path)')

    parser.add_argument('--objective_python_class', type=str, required=True,
                        help='Input classname for for the objective function')

    parser.add_argument('--input_parameters_file', type=str, required=True,
                        help='Input parameters file (assumed to be loadable with numpy.loadtxt)')

    parser.add_argument('--output_parameters_file', type=str, required=True,
                        help='Output parameters file where the optimized parameters are written')

    parser.add_argument('--optimizer_name', type=str, default='L-BFGS-B',
                        help='Name of the optimizer')

    parser.add_argument('--optimization_parameter_file', type=str,
                        help='Parameter file the optimization')

    parser.add_argument('--objective_parameter_file', type=str,
                        help='Parameter file the optimization')

    parser.add_argument('--start', type=int, default=0,
                        help='Starting index to read out of the parameter file, by default reads from start of file')

    parser.add_argument('--end', type=int, default=-1,
                        help='Ending index (exclusive) to read out of the parameter file, by default reads to end of file')

    parser.add_argument('--output_append', action='store_true',
                        help='Append output to end of file')

    parser.add_argument('--optimization_result_filename', type=str, default=None,
                        help='Where one should save the results.')

    parser.add_argument('--do_not_draw_new_samples', action='store_true',
                        help='Reuse old optimization values for next iteration')



    args = parser.parse_args()

    models = [tensorflow.keras.models.load_model(filename) for filename in args.input_model_files]

    if not args.do_not_draw_new_samples:
        if args.end != -1:
            starting_values = np.loadtxt(args.input_parameters_file)[args.start:args.end]
        else:
            starting_values = np.loadtxt(args.input_parameters_file)[args.start:]
    else:
        if args.end != -1:
            length = args.end - args.start
            starting_values = np.loadtxt(args.input_parameters_file)[args.start-length:args.end-length]
        else:
            raise Exception(f"You have to specify --end to something else than -1 when using --do_not_draw_new_samples")
    if args.optimization_parameter_file:
        with open (args.optimization_parameter_file) as config_file:
            optimization_configuration = json.load(config_file)
    else:
        optimization_configuration = {}


    if args.objective_parameter_file:
        with open (args.objective_parameter_file) as config_file:
            objective_configuration = json.load(config_file)
    else:
        objective_configuration = {}

    objective_function = ismo.objective_function.load_objective_function_from_python_file(args.objective_python_module,
                                                                                          args.objective_python_class,
                                                                                          objective_configuration)

    objective_function_dnn = ismo.objective_function.DNNObjectiveFunction(models, objective_function)

    optimizer = ismo.optimizers.create_optimizer(args.optimizer_name)

    optimized_parameters, optimization_results = ismo.optimizers.optimize_samples(
        starting_values=starting_values,
        J=objective_function_dnn,
        optimizer=optimizer)

    if args.optimization_result_filename is not None:
        if os.path.exists(args.optimization_result_filename):
            with open(args.optimization_result_filename, 'rb') as input_results_file:
                previous_optimization_results = pickle.load(input_results_file)
                optimization_results = previous_optimization_results + optimization_results

        with open(args.optimization_result_filename, 'wb') as output_results_file:
            pickle.dump(optimization_results, output_results_file)



    if args.output_append:
        if os.path.exists(args.output_parameters_file):
            if os.path.abspath(args.output_parameters_file) != os.path.abspath(args.input_parameters_file):
                raise Exception(f"When running with '--output_append', "
                                f"--output_parameters_file and --input_parameters_file need to be the same file, "
                                f"given {args.output_parameters_file} and {args.input_parameters_file}.")

            previous_optimized_parameters = np.loadtxt(args.output_parameters_file)

            if len(previous_optimized_parameters.shape) == 1:
                # In case of a 1D array, we need to make sure to treat is a two-dim array.
                previous_optimized_parameters = previous_optimized_parameters.reshape((previous_optimized_parameters.shape[0], 1))

            # Notice here we are *not* adding new samples, we are simply transforming the old ones.
            new_optimized_parameters = np.zeros_like(previous_optimized_parameters)

            starting_index = previous_optimized_parameters.shape[0] - optimized_parameters.shape[0]
            new_optimized_parameters[:starting_index, :] = previous_optimized_parameters[:starting_index,:]
            new_optimized_parameters[starting_index:, :] = optimized_parameters

            optimized_parameters = new_optimized_parameters
    np.savetxt(args.output_parameters_file, optimized_parameters)
