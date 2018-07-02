import codecs
import os
from datetime import timedelta, datetime
import pandas as pd
import logging

from StringIO import StringIO

import requests
from django.conf import settings
from django.forms.models import model_to_dict
from django.http.response import HttpResponse
from django.views.generic.base import View
from django.db.models import QuerySet
from django.shortcuts import reverse
from unicodecsv.py2 import UnicodeWriter

from dataloader.models import SamplingFeature, TimeSeriesResultValue, Unit, EquipmentModel, TimeSeriesResult, Result
from django.db.models.expressions import F
# Create your views here.
from django.utils.dateparse import parse_datetime
from rest_framework import exceptions
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from dataloaderinterface.forms import ResultForm, SiteSensorForm
from dataloaderinterface.models import SiteSensor, SiteRegistration, SensorOutput, SensorMeasurement
from dataloaderservices.auth import UUIDAuthentication
from dataloaderservices.serializers import OrganizationSerializer, SensorSerializer

from pytz import utc

from leafpack.models import LeafPack


class ResultApi(APIView):
    authentication_classes = (SessionAuthentication,)

    def post(self, request, format=None):
        form = ResultForm(data=request.POST)
        if form.is_valid():
            return Response({}, status=status.HTTP_200_OK)

        error_data = dict(form.errors)
        return Response(error_data, status=status.HTTP_206_PARTIAL_CONTENT)


class ModelVariablesApi(APIView):
    authentication_classes = (SessionAuthentication, )

    def get(self, request, format=None):
        if 'equipment_model_id' not in request.GET:
            return Response({'error': 'Equipment Model Id not received.'})

        equipment_model_id = request.GET['equipment_model_id']
        if equipment_model_id == '':
            return Response({'error': 'Empty Equipment Model Id received.'})

        equipment_model = EquipmentModel.objects.filter(pk=equipment_model_id).first()
        if not equipment_model:
            return Response({'error': 'Equipment Model not found.'})

        output = equipment_model.instrument_output_variables.values('variable', 'instrument_raw_output_unit')

        return Response(output)


class OutputVariablesApi(APIView):
    authentication_classes = (SessionAuthentication,)

    def get(self, request):
        output = SensorOutput.objects.for_filters()
        return Response(output)


class RegisterSensorApi(APIView):
    authentication_classes = (SessionAuthentication, )

    def post(self, request, format=None):
        form = SiteSensorForm(data=request.POST)

        if not form.is_valid():
            error_data = dict(form.errors)
            return Response(error_data, status=status.HTTP_206_PARTIAL_CONTENT)

        registration = form.cleaned_data['registration']
        sensor_output = form.cleaned_data['output_variable']
        height = form.cleaned_data['height']

        site_sensor = SiteSensor.objects.create(registration=registration, sensor_output=sensor_output, height=height)
        return Response(model_to_dict(site_sensor, fields=[field.name for field in site_sensor._meta.fields]), status=status.HTTP_201_CREATED)


class EditSensorApi(APIView):
    authentication_classes = (SessionAuthentication, )

    def post(self, request, format=None):
        if 'id' not in request.POST:
            return Response({'id': 'No sensor id in the request.'}, status=status.HTTP_400_BAD_REQUEST)

        sensor = SiteSensor.objects.filter(pk=request.POST['id']).first()
        if not sensor:
            return Response({'id': 'Sensor not found.'}, status=status.HTTP_404_NOT_FOUND)

        form = SiteSensorForm(data=request.POST, instance=sensor)

        if not form.is_valid():
            error_data = dict(form.errors)
            return Response(error_data, status=status.HTTP_206_PARTIAL_CONTENT)

        sensor.sensor_output = form.cleaned_data['output_variable']
        sensor.height = form.cleaned_data['height']
        sensor.save(update_fields=['sensor_output', 'height'])
        return Response(model_to_dict(sensor, fields=[field.name for field in sensor._meta.fields]), status=status.HTTP_202_ACCEPTED)


class DeleteSensorApi(APIView):
    authentication_classes = (SessionAuthentication, )

    def post(self, request, format=None):
        if 'id' not in request.POST:
            return Response({'id': 'No sensor id in the request.'}, status=status.HTTP_400_BAD_REQUEST)

        sensor = SiteSensor.objects.filter(pk=request.POST['id']).first()
        if not sensor:
            return Response({'id': 'Sensor not found.'}, status=status.HTTP_404_NOT_FOUND)

        deleted = sensor.delete()
        return Response(deleted, status=status.HTTP_202_ACCEPTED)


class DeleteLeafpackApi(APIView):
    authentication_classes = (SessionAuthentication, )

    def post(self, request, format=None):
        if 'id' not in request.POST:
            return Response({'id': 'No leafpack id in the request.'}, status=status.HTTP_400_BAD_REQUEST)

        leafpack = LeafPack.objects.filter(pk=request.POST['id']).first()
        if not leafpack:
            return Response({'id': 'Leafpack not found.'}, status=status.HTTP_404_NOT_FOUND)

        deleted = leafpack.delete()
        return Response(deleted, status=status.HTTP_202_ACCEPTED)


class OrganizationApi(APIView):
    authentication_classes = (SessionAuthentication, )

    def post(self, request, format=None):
        organization_serializer = OrganizationSerializer(data=request.data)

        if organization_serializer.is_valid():
            organization_serializer.save()
            return Response(organization_serializer.data, status=status.HTTP_201_CREATED)

        error_data = dict(organization_serializer.errors)
        return Response(error_data, status=status.HTTP_206_PARTIAL_CONTENT)


class FollowSiteApi(APIView):
    authentication_classes = (SessionAuthentication,)

    def post(self, request, format=None):
        action = request.data['action']
        sampling_feature_code = request.data['sampling_feature_code']
        site = SiteRegistration.objects.get(sampling_feature_code=sampling_feature_code)

        if action == 'follow':
            request.user.followed_sites.add(site)
        elif action == 'unfollow':
            request.user.followed_sites.remove(site)

        return Response({}, status.HTTP_200_OK)


class CSVDataApi(View):
    authentication_classes = ()

    date_format = '%Y-%m-%d %H:%M:%S'

    def get(self, request, *args, **kwargs):
        """
        Downloads csv file for given result id's.

        example request to download csv data for one series:
                curl -X GET http://localhost:8000/api.csv-values/?result_ids=100

        example request to download csv data for multiple series:
                curl -X GET http://localhost:8000/api.csv-values/?result_ids=100,101,102
        """

        if 'result_id' in request.GET:
            result_ids = [request.GET['result_id']]
        elif 'result_ids' in request.GET:
            result_ids = request.GET['result_ids'].split(',')
        else:
            return Response({'error': 'Result ID(s) not found.'})

        result_ids = filter(lambda x: len(x) > 0, result_ids)

        if not len(result_ids):
            return Response({'error': 'Result ID not found.'})

        try:
            filename, csv_file = CSVDataApi.get_csv_file(result_ids, request=request)
        except ValueError as e:
            return Response({'error': e.message})  # Time Series Result not found.

        response = HttpResponse(csv_file.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="%s.csv"' % filename
        return response

    @staticmethod
    def get_csv_file(result_ids, request=None):
        """
        Gathers time series data for the passed in result id's to generate a csv file for download
        """

        time_series_result = TimeSeriesResult.objects\
            .prefetch_related('values') \
            .prefetch_related('result__feature_action__action__people')\
            .select_related('result__feature_action__sampling_feature', 'result__variable')\
            .filter(pk__in=result_ids)

        if not time_series_result:
            raise ValueError('Time Series Result(s) not found (result id(s): {}).'.format(', '.join(result_ids)))

        csv_file = StringIO()
        csv_writer = UnicodeWriter(csv_file)
        csv_file.write(CSVDataApi.generate_metadata(time_series_result, request=request))
        csv_writer.writerow(CSVDataApi.get_csv_headers(time_series_result))
        csv_writer.writerows(CSVDataApi.get_data_values(time_series_result))

        result = time_series_result.first().result
        if len(result_ids) > 1:
            filename = "{}_TimeSeriesResults".format(result.feature_action.sampling_feature.sampling_feature_code)
        else:
            filename = "{0}_{1}_{2}".format(result.feature_action.sampling_feature.sampling_feature_code,
                                            result.variable.variable_code, result.result_id)

        return filename, csv_file

    @staticmethod
    def get_csv_headers(ts_results):  # type: ([TimeSeriesResult]) -> None
        headers = ['DateTime', 'TimeOffset', 'DateTimeUTC']
        var_codes = [ts_result.result.variable.variable_code for ts_result in ts_results]
        return headers + CSVDataApi.clean_variable_codes(var_codes)

    @staticmethod
    def clean_variable_codes(varcodes):  # type: ([str]) -> [str]
        """
        Looks for duplicate variable codes and appends a number if collisions exist.

        Example:
            codes = clean_variable_codes(['foo', 'bar', 'foo'])
            print(codes)
            # ['foo-1', 'bar', 'foo-2']
        """
        for varcode in varcodes:
            count = varcodes.count(varcode)
            if count > 1:
                counter = 1
                for i in range(0, len(varcodes)):
                    if varcodes[i] == varcode:
                        varcodes[i] = '{}-{}'.format(varcode, counter)
                        counter += 1
        return varcodes

    @staticmethod
    def get_data_values(time_series_results):  # type: (QuerySet) -> object

        def date_value_date(dv):  # type: (TimeSeriesResult) -> str
            dt = dv.value_datetime + timedelta(hours=dv.value_datetime_utc_offset)
            return dt.strftime(CSVDataApi.date_format)

        results_data = [result.values.all() for result in time_series_results]  # type: [TimeSeriesResultValue]
        max_data_len = max([len(result_data) for result_data in results_data])

        data = list()

        for i in range(0, max_data_len):
            dv = results_data[0][i]
            row = (
                date_value_date(dv),
                '{0}:00'.format(dv.value_datetime_utc_offset),
                dv.value_datetime.strftime(CSVDataApi.date_format),
            )

            for j in range(0, len(results_data)):
                try:
                    row += (results_data[j][i].data_value,)
                except IndexError:
                    row += ('',)

            data.append(row)

        return data

    @staticmethod
    def read_file(fname):
        fpath = os.path.join(os.path.dirname(__file__), 'csv_templates', fname)
        with codecs.open(fpath, 'r', encoding='utf-8') as fin:
            return fin.read()

    @staticmethod
    def generate_metadata(time_series_results, request=None):  # type: (QuerySet) -> str
        metadata = str()

        # Get the first TimeSeriesResult object and use it to get values for the
        # "Site Information" block in the header of the CSV
        tsr = time_series_results.first()
        site_sensor = SiteSensor.objects.select_related('registration').filter(result_id=tsr.result.result_id).first()
        metadata += CSVDataApi.read_file('site_information.txt').format(
            sampling_feature=site_sensor.registration.sampling_feature
        ).encode('utf-8')

        # Write Variable and Method Information data
        metadata += "# Variable and Method Information\n#---------------------------\n"
        variablemethodinfo_template = CSVDataApi.read_file('variable_and_method_information_template.txt')
        varcodes = [tsr.result.variable for tsr in time_series_results]
        varcodes = CSVDataApi.clean_variable_codes(varcodes)
        time_series_results_as_list = [tsr for tsr in time_series_results]
        for i in range(0, len(time_series_results_as_list)):
            # Yeah, so this is enumerating like this because of the need to append "-#"
            # to variable codes when there are duplicate variable codes. This is so the
            # column names can be distinguished easily. This rather ugly solution is
            # so the CSV files can be formatted as requested by the gods.
            tsr = time_series_results_as_list[i]
            varcode = varcodes[i]

            metadata += variablemethodinfo_template.format(
                variable_code=varcode,
                r=tsr.result,
                v=tsr.result.variable,
                u=tsr.result.unit
            )
        metadata += "#\n"

        if len(time_series_results) == 1:
            # If there's only one timeseriesresult, add the variable and unit information block.
            # When there are multiple timeseriesresults, this part of the CSV becomes cluttered
            # and unreadable.
            metadata += CSVDataApi.read_file('variable_and_unit_information.txt').format(
                variable=tsr.result.variable,
                unit=tsr.result.unit
            )

        # Write Source Information data

        # affiliation = tsr.result.feature_action.action.people.first()
        affiliation = site_sensor.registration.odm2_affiliation
        annotation = tsr.result.annotations.first()
        citation = annotation.citation.title if annotation and annotation.citation else ''

        if request:
            source_link = request.build_absolute_uri(reverse('site_detail', kwargs={
                'sampling_feature_code': site_sensor.registration.sampling_feature_code}))
        else:
            source_link = reverse('site_detail', kwargs={
                'sampling_feature_code': site_sensor.registration.sampling_feature_code})

        metadata += CSVDataApi.read_file('source_info_template.txt').format(
            affiliation=affiliation,
            citation=citation,
            source_link=source_link
        )

        return metadata


class TimeSeriesValuesApi(APIView):
    authentication_classes = (UUIDAuthentication, )

    def post(self, request, format=None):
        #  make sure that the data is in the request (sampling_feature, timestamp(?), ...) if not return error response
        # if 'sampling_feature' not in request.data or 'timestamp' not in request.data:
        if not all(key in request.data for key in ('timestamp', 'sampling_feature')):
            raise exceptions.ParseError("Required data not found in request.")

        # parse the received timestamp
        try:
            measurement_datetime = parse_datetime(request.data['timestamp'])
        except ValueError:
            raise exceptions.ParseError('The timestamp value is not valid.')

        if not measurement_datetime:
            raise exceptions.ParseError('The timestamp value is not well formatted.')

        if measurement_datetime.utcoffset() is None:
            raise exceptions.ParseError('The timestamp value requires timezone information.')

        utc_offset = int(measurement_datetime.utcoffset().total_seconds() / timedelta(hours=1).total_seconds())

        # saving datetimes in utc time now.
        measurement_datetime = measurement_datetime.replace(tzinfo=None) - timedelta(hours=utc_offset)

        # get odm2 sampling feature if it matches sampling feature uuid sent
        sampling_feature = SamplingFeature.objects.filter(sampling_feature_uuid__exact=request.data['sampling_feature']).first()
        if not sampling_feature:
            raise exceptions.ParseError('Sampling Feature code does not match any existing site.')

        # get all feature actions related to the sampling feature, along with the results, results variables, and actions.
        feature_actions = sampling_feature.feature_actions.prefetch_related('results__variable', 'action').all()
        for feature_action in feature_actions:
            result = feature_action.results.all().first()
            site_sensor = SiteSensor.objects.filter(result_id=result.result_id).first()

            is_first_value = result.value_count == 0

            # don't create a new TimeSeriesValue for results that are not included in the request
            if str(result.result_uuid) not in request.data:
                continue

            result_value = TimeSeriesResultValue(
                result_id=result.result_id,
                value_datetime_utc_offset=utc_offset,
                value_datetime=measurement_datetime,
                censor_code_id='Not censored',
                quality_code_id='None',
                time_aggregation_interval=1,
                time_aggregation_interval_unit=Unit.objects.get(unit_name='hour minute'),
                data_value=request.data[str(result.result_uuid)]
            )

            try:
                result_value.save()
            except Exception as e:
                # continue adding the remaining measurements in the request.
                # TODO: use a logger to log the failed request information.
                continue
                # raise exceptions.ParseError("{variable_code} value not saved {exception_message}".format(
                #     variable_code=result.variable.variable_code, exception_message=e
                # ))

            result.value_count = F('value_count') + 1
            result.result_datetime = measurement_datetime
            result.result_datetime_utc_offset = utc_offset

            # delete last measurement
            last_measurement = SensorMeasurement.objects.filter(sensor=site_sensor).first()
            last_measurement and last_measurement.delete()

            # create new 'last' measurement
            SensorMeasurement.objects.create(
                sensor=site_sensor,
                value_datetime=result_value.value_datetime,
                value_datetime_utc_offset=timedelta(hours=result_value.value_datetime_utc_offset),
                data_value=result_value.data_value
            )

            if is_first_value:
                result.valid_datetime = measurement_datetime
                result.valid_datetime_utc_offset = utc_offset
                site_sensor.activation_date = measurement_datetime
                site_sensor.activation_date_utc_offset = utc_offset

                site_sensor.save(update_fields=[
                    'activation_date', 'activation_date_utc_offset'
                ])

                if not site_sensor.registration.deployment_date:
                    site_sensor.registration.deployment_date = measurement_datetime
                    site_sensor.registration.deployment_date_utc_offset = utc_offset
                    site_sensor.registration.save(update_fields=['deployment_date'])

            result.save(update_fields=[
                'result_datetime', 'value_count', 'result_datetime_utc_offset',
                'valid_datetime', 'valid_datetime_utc_offset'
            ])

            # Insert data value into influx instance.
            influx_request_url = settings.INFLUX_UPDATE_URL
            influx_request_body = settings.INFLUX_UPDATE_BODY.format(
                result_uuid=str(site_sensor.result_uuid).replace('-', '_'),
                data_value=result_value.data_value,
                utc_offset=result_value.value_datetime_utc_offset,
                timestamp_s=long((result_value.value_datetime - datetime.utcfromtimestamp(0)).total_seconds()),
            )
            requests.post(influx_request_url, influx_request_body.encode())

        return Response({}, status.HTTP_201_CREATED)
