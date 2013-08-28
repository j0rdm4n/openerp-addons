# -*- coding: utf-8 -*-

from openerp import SUPERUSER_ID
from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp.tools.translate import _
from openerp.addons import website_sale

from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp import tools
import urllib
import werkzeug


class website_event(http.Controller):

    @http.route(['/event/', '/event/page/<int:page>/'], type='http', auth="public")
    def events(self, page=1, **searches):
        website = request.registry['website']
        event_obj = request.registry['event.event']

        searches.setdefault('date', 'all')
        searches.setdefault('type', 'all')
        searches.setdefault('country', 'all')

        domain_search = {}

        def sd(date):
            return date.strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT)
        today = datetime.today()
        dates = [
            ['all', _('All Dates'), [(1, "=", 1)], 0],
            ['today', _('Today'), [
                ("date_begin", ">", sd(today)),
                ("date_begin", "<", sd(today + relativedelta(days=1)))],
                0],
            ['tomorrow', _('Tomorrow'), [
                ("date_begin", ">", sd(today + relativedelta(days=1))),
                ("date_begin", "<", sd(today + relativedelta(days=2)))],
                0],
            ['week', _('This Week'), [
                ("date_begin", ">=", sd(today + relativedelta(days=-today.weekday()))),
                ("date_begin", "<", sd(today  + relativedelta(days=6-today.weekday())))],
                0],
            ['nextweek', _('Next Week'), [
                ("date_begin", ">=", sd(today + relativedelta(days=7-today.weekday()))),
                ("date_begin", "<", sd(today  + relativedelta(days=13-today.weekday())))],
                0],
            ['month', _('This month'), [
                ("date_begin", ">=", sd(today.replace(day=1) + relativedelta(months=1))),
                ("date_begin", "<", sd(today.replace(day=1)  + relativedelta(months=1)))],
                0],
        ]

        # search domains
        for date in dates:
            if searches.get("date") == date[0]:
                domain_search["date"] = date[2]
        if searches.get("type", "all") != 'all':
            domain_search["type"] = [("type", "=", int(searches.get("type")))]
        if searches.get("country", "all") != 'all':
            domain_search["country"] = [("country_id", "=", int(searches.get("country")))]

        def dom_without(without):
            domain = SUPERUSER_ID != request.uid and [('website_published', '=', True)] or [(1, "=", 1)]
            for key, search in domain_search.items():
                if key != without:
                    domain += search
            return domain

        # count by domains without self search
        for date in dates:
            date[3] = event_obj.search(request.cr, request.uid, dom_without('date') + date[2], count=True)

        domain = dom_without('type')
        types = event_obj.read_group(request.cr, request.uid, domain, ["id", "type"], groupby="type", orderby="type")
        types.insert(0, {'type_count': event_obj.search(request.cr, request.uid, domain, count=True), 'type': ("all", _("All Categories"))})

        domain = dom_without('country')
        countries = event_obj.read_group(request.cr, request.uid, domain, ["id", "country_id"], groupby="country_id", orderby="country_id")
        countries.insert(0, {'country_id_count': event_obj.search(request.cr, request.uid, domain, count=True), 'country_id': ("all", _("All Countries"))})

        step = 5
        event_count = event_obj.search(request.cr, request.uid, dom_without("none"), count=True)
        pager = website.pager(url="/event/", total=event_count, page=page, step=step, scope=5)
        obj_ids = event_obj.search(request.cr, request.uid, dom_without("none"), limit=step, offset=pager['offset'], order="date_begin DESC")

        values = website.get_rendering_context({
            'event_ids': event_obj.browse(request.cr, request.uid, obj_ids),
            'dates': dates,
            'types': types,
            'countries': countries,
            'pager': pager,
            'searches': searches,
            'search_path': "?%s" % urllib.urlencode(searches),
        })

        return website.render("website_event.index", values)

    @http.route(['/event/<int:event_id>'], type='http', auth="public")
    def event(self, event_id=None, **post):
        website = request.registry['website']
        event = request.registry['event.event'].browse(request.cr, request.uid, event_id, {'show_address': 1})
        values = website.get_rendering_context({
            'event_id': event,
            'range': range
        })
        return website.render("website_event.detail", values)

    @http.route(['/event/<int:event_id>/add_cart'], type='http', auth="public")
    def add_cart(self, event_id=None, **post):
        website = request.registry['website']
        user_obj = request.registry['res.users']
        order_line_obj = request.registry.get('sale.order.line')
        ticket_obj = request.registry.get('event.event.ticket')

        order = website.get_rendering_context()['order']
        if not order:
            order = website_sale.controllers.main.get_order()

        partner_id = user_obj.browse(request.cr, SUPERUSER_ID, request.uid).partner_id.id

        context = {}

        fields = [k for k, v in order_line_obj._columns.items()]
        values = order_line_obj.default_get(request.cr, SUPERUSER_ID, fields, context=context)

        _values = None
        for key, value in post.items():
            quantity = int(value)
            ticket_id = key.split("-")[0] == 'ticket' and int(key.split("-")[1]) or None
            if not ticket_id or not quantity:
                continue
            ticket = ticket_obj.browse(request.cr, request.uid, ticket_id)

            values['product_id'] = ticket.product_id.id
            values['event_id'] = ticket.event_id.id
            values['event_ticket_id'] = ticket.id
            values['product_uom_qty'] = quantity
            values['price_unit'] = ticket.price
            values['order_id'] = order.id
            values['name'] = "%s: %s" % (ticket.event_id.name, ticket.name)

            ticket.check_registration_limits_before(quantity)

            # change and record value
            pricelist_id = order.pricelist_id and order.pricelist_id.id or False
            _values = order_line_obj.product_id_change(request.cr, SUPERUSER_ID, [], pricelist_id, ticket.product_id.id, partner_id=partner_id, context=context)['value']
            _values.update(values)

            order_line_id = order_line_obj.create(request.cr, SUPERUSER_ID, _values, context=context)
            order.write({'order_line': [(4, order_line_id)]}, context=context)

        if not _values:
            return werkzeug.utils.redirect("/event/%s/" % event_id)
        return werkzeug.utils.redirect("/shop/checkout")
