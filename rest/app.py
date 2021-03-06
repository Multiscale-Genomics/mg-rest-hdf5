"""
.. See the NOTICE file distributed with this work for additional information
   regarding copyright ownership.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

from __future__ import print_function

import os
import sys

from flask import Flask, make_response, request
from flask_restful import Api, Resource

from dmp import dmp
from reader.hdf5_adjacency import adjacency

from mg_rest_util.mg_auth import authorized

APP = Flask(__name__)
# APP.config['DEBUG'] = True

REST_API = Api(APP)

@REST_API.representation('application/tsv')
def output_tsv(data, code, headers=None):
    """
    TSV representation for interactions
    """
    if request.endpoint == "values":
        outstr = ''
        for value in data["values"]:
            outstr += str(value["chrA"]) + "\t" + str(value["startA"]) + "\t"
            outstr += str(value["chrB"]) + "\t" + str(value["startB"]) + "\t"
            outstr += str(value["value"]) + "\n"
        resp = make_response(outstr, code)
        resp.headers.extend(headers or {})
        return resp

def help_usage(error_message, status_code,
               parameters_required, parameters_provided):
    """
    Usage Help

    Description of the basic usage patterns for GET functions for the app,
    including any parameters that were provided byt he user along with the
    available parameters that are required/optional.

    Parameters
    ----------
    error_message : str | None
        Error message detailing what has gone wrong. If there are no errors then
        None should be passed.
    status_code : int
        HTTP status code. A full list of codes can be found at the
        `W3<https://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html>`
    parameters_required : list
        List of the text names for each paramter required by the end point. An
        empty list should be provided if there are no parameters required
    parameters_provided : dict
        Dictionary of the parameters and the matching values provided by the
        user. An empyt dictionary should be passed if there were no parameters
        provided by the user.

    Returns
    -------
    str
        JSON formated status message to display to the user
    """
    parameters = {
        "file_id" : ["File ID", "str", "REQUIRED"],
        "chrom" : ["Chromosome", "str", "REQUIRED"],
        "start" : ["Start", "int", "REQUIRED"],
        "end" : ["End", "int", "REQUIRED"],
        "res"     : ["Resolution", "int", "REQUIRED"],
        "limit_chr" : [
            "Limit interactions to interacting with a specific chromosome",
            "str", "OPTIONAL"],
        "limit_start" : [
            "Limits interactions based on a region within the chromosome defined by the limit_chr parameter. REQUIRES that limit_chr and limit_end are defined",
            "int", "OPTIONAL"],
        "limit_end" : [
            "Limits interactions based on a region within the chromosome defined by the limit_chr parameter. REQUIRES that limit_chr and limit_start are defined",
            "int", "OPTIONAL"],
        "pos_x" : ["Position i", "int", "REQUIRED"],
        "pos_y" : ["Position j", "int", "REQUIRED"],
        "type" : ["add_meta|remove_meta", "str", "REQUIRED"]
    }

    used_param = {k : parameters[k] for k in parameters_required if k in parameters}

    usage = {
        '_links' : {
            '_self' : request.base_url,
            '_parent' : request.url_root + 'mug/api/adjacency'
        },
        'parameters' : used_param
    }
    message = {
        'usage' : usage,
        'status_code' : status_code
    }

    if parameters_provided:
        message['provided_parameters'] = parameters_provided

    if error_message != None:
        message['error'] = error_message

    return message


class GetEndPoints(Resource):
    """
    Class to handle the http requests for returning information about the end
    points
    """

    def get(self):
        """
        GET list all end points

        List of all of the end points for the current service.

        Example
        -------
        .. code-block:: none
           :linenos:

           curl -X GET http://localhost:5001/mug/api/adjacency
        """
        return {
            '_links': {
                '_self': request.base_url,
                '_details': request.url_root + 'mug/api/adjacency/details',
                '_getInteractions': request.url_root + 'mug/api/adjacency/getInteractions',
                '_getValue': request.url_root + 'mug/api/adjacency/getValue',
                '_ping': request.url_root + 'mug/api/adjacency/ping',
                '_parent': request.url_root + 'mug/api'
            }
        }


class GetDetails(Resource):
    """
    Class to handle the http requests for the size of the chromosome, the
    number of bins and available resolutions
    """

    @authorized
    def get(self, user_id):
        """
        GET List details from the file

        Call to list the available chromosomes and resolutions within a dataset

        Parameters
        ----------
        user_id : str
            User ID
        file_id : str
            Identifier of the file to retrieve data from

        Returns
        -------
        dict
            chromosomes : list
                List of the available chromosomes and their length
            resolutions : list
                List of the resolutions for the dataset

        Examples
        --------
        .. code-block:: none
           :linenos:

           curl -X GET
               -H "Authorization: Bearer teststring"
               http://localhost:5001/mug/api/adjacency/details?file_id=test_file

        """
        if user_id is not None:
            file_id = request.args.get('file_id')

            params_required = ['file_id']
            params = [user_id, file_id]

            # Display the parameters available
            if sum([x is None for x in params]) == len(params):
                return {"usage": "test"}
                #return help_usage(None, 200, params_required, {})

            # ERROR - one of the required parameters is NoneType
            if sum([x is not None for x in params]) != len(params):
                return help_usage(
                    'MissingParameters', 400, params_required,
                    {'file_id' : file_id}
                )

            #request_path = request.path
            #rp = request_path.split("/")

            hdf5_handle = adjacency(user_id["user_id"], file_id)
            h5_data = hdf5_handle.get_details()
            hdf5_handle.close()

            return {
                '_links': {
                    '_self': request.base_url,
                    '_parent': request.url_root + 'mug/api/adjacency'
                },
                'chromosomes' : [
                    {'chromosome' : c[0], 'length' : c[1]} for c in h5_data["chromosomes"]
                ],
                'resolutions' : h5_data['resolutions']
            }

        return help_usage('Forbidden', 403, params_required, {})


class GetInteractions(Resource):
    """
    Class to handle the http requests for retrieving ranges of interactions from
    a given dataset
    """

    @authorized
    def get(self, user_id):
        """
        GET List details from the file

        Call to list the available chromosomes and resolutions within a dataset

        Parameters
        ----------
        user_id : str
            User ID
        file_id : str
            Identifier of the file to retrieve data from
        chrom : str
            Chromosome identifier (1, 2, 3, chr1, chr2, chr3, I, II, III, etc)
            for the chromosome of interest
        start : int
            Start position for a selected region
        end : int
            End position for a selected region
        res : int
            Resolution of the dataset requested
        limit_chr : str
            Limit the interactions returned to those between chr and
        limit_start : int
            Start position for a specific interacting chromosomal region. This
            is to be used in conjunction with the limit_chr parameter
        limit_end : int
            End position for a specific interacting chromosomal region This
            is to be used in conjunction with the limit_chr parameter

        Returns
        -------
        dict
            chr : str
                Chromosome ID
            resolutions : list
                List of the resolutions for the dataset
            start : int
                Start position for a selected region
            end : int
                End position for a selected region
            res : int
                Resolution of the dataset requested
            limit_chr : str
                Limit the interactions returned to those between chr and
            limit_start : int
                Start position for a specific interacting chromosomal region.
                This is to be used in conjunction with the limit_chr parameter
            limit_end : int
                End position for a specific interacting chromosomal region This
                is to be used in conjunction with the limit_chr parameter
            values : list
                List of values for each window of the region of a given
                resolution
            log : list
                List of errors that have occurred

        Examples
        --------
        .. code-block:: none
           :linenos:

           curl -X GET
               -H "Authorization: Bearer teststring"
               http://localhost:5001/mug/api/adjacency/getInteractions?file_id=test_file&chr=<chr_id>&res=<res>

        Notes
        -----
        By default this is in JSON format. If the output is required in a tab
        separated format then the following needs to be specified in the header
        of the request:

        .. code-block:: none
           :linenos:

           curl -X GET
               -H "Accept: application/tsv"
               -H "Authorization: Bearer teststring"
               http://localhost:5001/mug/api/adjacency/getInteractions?file_id=test_file&chr=<chr_id>&res=<res>


        This will return the values from the JSON format in the following order

        1. Chromosome 1
        2. Starting position for chromosome 1
        3. Chromosome 2
        4. Starting position for chromosome 2
        5. Value

        """
        if user_id is not None:
            file_id = request.args.get('file_id')
            chr_id = request.args.get('chr')
            start = request.args.get('start')
            end = request.args.get('end')
            resolution = request.args.get('res')
            limit_chr = request.args.get('limit_chr')
            limit_start = request.args.get('limit_start')
            limit_end = request.args.get('limit_end')
            no_links = request.args.get('no_links')

            params_required = [
                'user_id', 'file_id', 'chr_id', 'start', 'end', 'res',
                'limit_chr', 'limit_start', 'limit_end']
            params = [user_id, file_id, chr_id, start, end, resolution]

            # Display the parameters available
            if sum([x is None for x in params]) == len(params):
                return help_usage(None, 200, params_required, {})

            # ERROR - one of the required parameters is NoneType
            if sum([x is not None for x in params]) != len(params):
                return help_usage(
                    'MissingParameters', 400, params_required,
                    {
                        'file_id' : file_id,
                        'chr' : chr_id, 'start' : start, 'end' : end,
                        'res' : resolution, 'limit_chr' : limit_chr,
                        'limit_start' : limit_start, 'limit_end' : limit_end
                    }
                )

            try:
                start = int(start)
                end = int(end)
                resolution = int(resolution)
            except ValueError:
                # ERROR - one of the parameters is not of integer type
                return help_usage(
                    'IncorrectParameterType', 400, params_required,
                    {
                        'file_id' : file_id,
                        'chr' : chr_id, 'start' : start, 'end' : end,
                        'res' : resolution, 'limit_chr' : limit_chr
                    }
                )

            hdf5_handle = adjacency(user_id["user_id"], file_id, resolution)
            details = hdf5_handle.get_details()
            #print("Details:", details)

            # ERROR - the requested resolution is not available
            if resolution not in details["resolutions"]:
                return help_usage(
                    'Resolution Not Available', 400, params_required,
                    {
                        'file_id' : file_id,
                        'chr' : chr_id, 'start' : start, 'end' : end,
                        'res' : resolution, 'limit_chr' : limit_chr,
                        'limit_start' : limit_start, 'limit_end' : limit_end
                    }
                )

            if limit_start is not None or limit_end is not None:
                if limit_chr is None:
                    return help_usage(
                        'MissingParameters', 400, params_required,
                        {
                            'file_id' : file_id,
                            'chr' : chr_id, 'start' : start, 'end' : end,
                            'res' : resolution, 'limit_chr' : limit_chr,
                            'limit_start' : limit_start, 'limit_end' : limit_end
                        }
                    )
                try:
                    limit_start = int(limit_start)
                    limit_end = int(limit_end)
                except ValueError:
                    # ERROR - one of the parameters is not of integer type
                    return help_usage(
                        'IncorrectParameterType', 400, params_required,
                        {
                            'file_id' : file_id,
                            'chr' : chr_id, 'start' : start, 'end' : end,
                            'res' : resolution, 'limit_chr' : limit_chr,
                            'limit_start' : limit_start, 'limit_end' : limit_end
                        }
                    )

            value_url = request.url_root + 'mug/api/adjacency/getValue'

            h5_data = hdf5_handle.get_range(
                chr_id, start, end, limit_chr, limit_start, limit_end,
                value_url, no_links)
            hdf5_handle.close()
            #app.logger.warn(h5_data["log"])

            return {
                '_links': {
                    '_self': request.url,
                    '_parent': request.url_root + 'mug/api/adjacency'
                },
                'resolution': resolution,
                'chr': chr_id,
                'start': start,
                'end': end,
                'limit_chr': limit_chr,
                'limit_start' : limit_start,
                'limit_end' : limit_end,
                'interaction_count': len(h5_data["results"]),
                'values': h5_data["results"],
                'log': h5_data["log"]
            }

        return help_usage(
            'Forbidden', 403,
            [
                'file_id', 'chr_id', 'start', 'end', 'res',
                'limit_chr', 'limit_start', 'limit_end'
            ], {})

class GetValue(Resource):
    """
    Class to handle the http requests for retrieving a single value from a given
    dataset
    """

    @authorized
    def get(self, user_id):
        """
        GET single value

        Call to get a single value for a spcific bin x bin location

        Parameters
        ----------
        user_id : str
            User ID
        file_id : str
            Identifier of the file to retrieve data from
        pos_x : int
            Location of the window on the first region of interest
        pos_y : int
            Location of the window on the second region of interest
        res : int
            Resolution of the dataset requested

        Returns
        -------
        dict
            chrA : str
                Chromosome ID 1
            chrB : str
                Chromosome ID 2
            resolution : int
                Resolution of the bin of interest
            pos_x : int
                Location of the window on the first region of interest
            pos_y : int
                Location of the window on the second region of interest
                is to be used in conjunction with the limit_chr parameter
            values : list
                List of values for each window of the region of a given
                resolution

        Examples
        --------
        .. code-block:: none
           :linenos:

           curl -X GET
               -H "Authorization: Bearer teststring"
               http://localhost:5001/mug/api/adjacency/getValue?file_id=test_file&chr=<chr_id>&res=<res>
        """
        if user_id is not None:
            file_id = request.args.get('file_id')
            resolution = request.args.get('res')
            pos_x = request.args.get('pos_x')
            pos_y = request.args.get('pos_y')

            params_required = ['user_id', 'file_id', 'res', 'pos_x', 'pos_y']
            params = [user_id, file_id, resolution, pos_x, pos_y]

            # Display the parameters available
            if sum([x is None for x in params]) == len(params):
                return help_usage(None, 200, params_required, {})

            # ERROR - one of the required parameters is NoneType
            if sum([x is not None for x in params]) != len(params):
                return help_usage(
                    'MissingParameters', 400, params_required,
                    {
                        'file_id' : file_id,
                        'resolution' : resolution, 'pos_x' : pos_x, 'pos_y' : pos_y
                    }
                )

            try:
                pos_x = int(pos_x)
                pos_y = int(pos_y)
                resolution = int(resolution)
            except ValueError:
                # ERROR - one of the parameters is not of integer type
                return help_usage(
                    'IncorrectParameterType', 400, params_required,
                    {
                        'file_id' : file_id,
                        'resolution' : resolution, 'pos_x' : pos_x, 'pos_y' : pos_y
                    }
                )

            h5_handle = adjacency(user_id["user_id"], file_id, resolution)
            #meta_data = h5.get_details()
            #print("chr_param:", meta_data["chr_param"])
            value = h5_handle.get_value(pos_x, pos_y)

            chr_a_id = h5_handle.get_chromosome_from_array_index(pos_x)
            chr_b_id = h5_handle.get_chromosome_from_array_index(pos_y)

            h5_handle.close()

            return {
                "_links": {
                    "_self": request.url_root + "mug/api/adjacency/getValue?file_id=" + str(file_id) + "&res=" + str(resolution) + "&pos_x=" + str(pos_x) + "&pos_y=" + str(pos_y)
                },
                "chrA": chr_a_id,
                "chrB": chr_b_id,
                "resolution": resolution,
                "pos_x": pos_x,
                "pos_y": pos_y,
                "value": int(value)
            }

        return help_usage("Forbidden", 403, ["file_id", "res", "pos_x", "pos_y"], {})

class Ping(Resource):
    """
    Class to handle the http requests to ping a service
    """

    @staticmethod
    def get():
        """
        GET Status

        List the current status of the service along with the relevant
        information about the version.

        Examples
        --------
        .. code-block:: none
           :linenos:

           curl -X GET http://localhost:5001/mug/api/adjacency/ping

        """
        from . import release
        res = {
            "status":  "ready",
            "version": release.__version__,
            "author":  release.__author__,
            "license": release.__license__,
            "name":    release.__rest_name__,
            "description": release.__description__,
            "_links" : {
                '_self' : request.url_root + 'mug/api/adjacency/ping',
                '_parent' : request.url_root + 'mug/api/adjacency'
            }
        }
        return res

#
# For the services where there needs to be an extra layer (adjacency lists),
# then there needs to be a way of forwarding for this. But the majority of
# things can be redirected to the raw files for use as a track.
#

sys._auth_meta_json = os.path.dirname(os.path.realpath(__file__)) + '/auth_meta.json'

# Define the URIs and their matching methods

#   List the available end points for this service
REST_API.add_resource(GetEndPoints, "/mug/api/adjacency", endpoint='adjacency_root')

#   Show the size of the chromosome, the number of bins and available resolutions
REST_API.add_resource(GetDetails, "/mug/api/adjacency/details", endpoint='meta_data')

#   List the interactions for a given region
REST_API.add_resource(GetInteractions, "/mug/api/adjacency/getInteractions", endpoint='values')

#   Get a specific edge value for an interaction
REST_API.add_resource(GetValue, "/mug/api/adjacency/getValue", endpoint="value")

#   Service ping
REST_API.add_resource(Ping, "/mug/api/adjacency/ping", endpoint='adjacency-ping')


# Initialise the server
if __name__ == "__main__":
    APP.run()
