# -*- coding: utf-8 -*-

from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp.addons.website import website

from urllib import quote_plus

class contactus(http.Controller):

    @website.route(['/crm/contactus'], type='http', auth="admin")
    def contactus(self, *arg, **post):
        post['user_id'] = False
        request.registry['crm.lead'].create(request.cr, request.uid, post)
        company = request.webcontext['res_company']
        values = {
            'google_map_url': "http://maps.googleapis.com/maps/api/staticmap?center=%s&sensor=false&zoom=8&size=298x298" % quote_plus('%s, %s %s, %s' % (company.street, company.city, company.zip, company.country_id and company.country_id.name_get()[0][1] or ''))
        }
        return request.webcontext.render("website_crm.thanks", values)

# vim:expandtab:tabstop=4:softtabstop=4:shiftwidth=4:
