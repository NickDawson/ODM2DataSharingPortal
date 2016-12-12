from __future__ import unicode_literals

import abc

from django.db import models

# region ODM2 Core models
from django.db.models.query_utils import Q


class ODM2QuerySet(models.QuerySet):
    def for_display(self):
        return self.all()

    for_display.queryset_only = True


class AffiliationQuerySet(ODM2QuerySet):
    def for_display(self):
        return self.select_related('person').prefetch_related('organization')


class MethodQuerySet(ODM2QuerySet):
    def instrument_deployment_methods(self):
        return self.filter(method_type='Instrument deployment')


class ActionQuerySet(ODM2QuerySet):
    def deployments(self):
        return self.filter(Q(action_type='Equipment deployment') | Q(action_type='Instrument deployment'))

    def equipment_deployments(self):
        return self.filter(action_type='Equipment deployment')

    def instrument_deployments(self):
        return self.filter(action_type='Instrument deployment')


class ActionByQuerySet(ODM2QuerySet):
    def for_display(self):
        return self.select_related('action').prefetch_related('affiliation__person', 'affiliation__organization')


class FeatureActionQuerySet(ODM2QuerySet):
    def for_display(self):
        return self.select_related('action').prefetch_related('sampling_feature')


class RelatedActionManager(models.Manager):
    def get_queryset(self):
        queryset = super(RelatedActionManager, self).get_queryset()
        return queryset.prefetch_related('related_action', 'action')


class ResultManager(models.Manager):
    def get_queryset(self):
        queryset = super(ResultManager, self).get_queryset()
        return queryset.prefetch_related(
            'variable', 'unit', 'taxonomic_classifier', 'processing_level'
        )


class DataLoggerFileManager(models.Manager):
    def get_queryset(self):
        queryset = super(DataLoggerFileManager, self).get_queryset()
        return queryset.prefetch_related('program')


class DataLoggerFileColumnManager(models.Manager):
    def get_queryset(self):
        queryset = super(DataLoggerFileColumnManager, self).get_queryset()
        return queryset.DataLoggerFileColumnManager('result')

# endregion

# region ODM2 Equipment Extension


class EquipmentModelManager(models.Manager):
    def get_queryset(self):
        queryset = super(EquipmentModelManager, self).get_queryset()
        return queryset.prefetch_related('model_manufacturer')


class InstrumentOutputVariableManager(models.Manager):
    def get_queryset(self):
        queryset = super(InstrumentOutputVariableManager, self).get_queryset()
        return queryset.prefetch_related('model', 'variable', 'instrument_method', 'instrument_raw_output_unit')


class EquipmentManager(models.Manager):
    def get_queryset(self):
        queryset = super(EquipmentManager, self).get_queryset()
        return queryset.prefetch_related('equipment_model', 'equipment_owner', 'equipment_vendor')


class CalibrationReferenceEquipmentManager(models.Manager):
    def get_queryset(self):
        queryset = super(CalibrationReferenceEquipmentManager, self).get_queryset()
        return queryset.prefetch_related('action', 'equipment')


class EquipmentUsedManager(models.Manager):
    def get_queryset(self):
        queryset = super(EquipmentUsedManager, self).get_queryset()
        return queryset.prefetch_related('action', 'equipment')


class MaintenanceActionManager(models.Manager):
    def get_queryset(self):
        queryset = super(MaintenanceActionManager, self).get_queryset()
        return queryset.prefetch_related('action')


class RelatedEquipmentManager(models.Manager):
    def get_queryset(self):
        queryset = super(RelatedEquipmentManager, self).get_queryset()
        return queryset.prefetch_related('equipment', 'related_equipment')


class CalibrationActionManager(models.Manager):
    def get_queryset(self):
        queryset = super(CalibrationActionManager, self).get_queryset()
        return queryset.prefetch_related('instrument_output_variable')

# endregion

# class TimeSeriesResultValuesManager(models.Manager):
#     def get_queryset(self):
#         queryset = super(CalibrationActionManager, self).get_queryset()
#         return queryset.prefetch_related('instrument_output_variable')
