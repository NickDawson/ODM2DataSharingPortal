from dataloader.models import SamplingFeature, Result
from django import template

from dataloaderinterface.models import SiteRegistration

register = template.Library()

@register.filter(name='get_site_sensor')
def get_site_sensor(site, variable_code):
    if not isinstance(site, SiteRegistration) or not site.status_sensors:
        return

    return next((sensor for sensor in site.status_sensors if sensor.variable_code==variable_code), None)


@register.filter(name='can_administer_site')
def can_administer_site():
    pass
    # return DeviceRegistration.objects.filter(deployment_sampling_feature_uuid__exact=sampling_feature.sampling_feature_uuid).first()
