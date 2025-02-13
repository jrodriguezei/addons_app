/** @odoo-module */
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { FilterValue } from "@spreadsheet/global_filters/components/filter_value/filter_value";
export class DomainSelectorActivityAutocomplete extends MultiRecordSelector {
    static props = {
        ...MultiRecordSelector.props,
        resIds: true, //resIds could be an array of ids or an array of expressions
        resModel: "mail.activity",
    };  
}
MailActivityFilterValue.template = "activity_edition.FilterValue";
MailActivityFilterValue.components = {FilterValue};
MailActivityFilterValue.props = {
    filter: Object,
    model: Object,
};