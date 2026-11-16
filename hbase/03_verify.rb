# Replace this sample ID if testing a different dataset.
describe 'dewa_meter_status'
get 'dewa_meter_status', 'MAC000002'
scan 'dewa_meter_status', {LIMIT => 10}
scan 'dewa_meter_status', {FILTER => "SingleColumnValueFilter('a','status',=,'binary:ALERT',true,true)", LIMIT => 10}
exit
