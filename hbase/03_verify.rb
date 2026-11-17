# MAC000016 is in data/sample; change the ID when testing other meters.
describe 'dewa_meter_status'
get 'dewa_meter_status', 'MAC000016'
scan 'dewa_meter_status', {LIMIT => 10}
scan 'dewa_meter_status', {FILTER => "SingleColumnValueFilter('a','status',=,'binary:ALERT',true,true)", LIMIT => 10}
exit
