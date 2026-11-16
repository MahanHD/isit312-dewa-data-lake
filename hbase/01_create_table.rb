# Run with: hbase shell -n /workspace/hbase/01_create_table.rb
unless exists 'dewa_meter_status'
  create 'dewa_meter_status', {NAME => 'r', VERSIONS => 1}, {NAME => 'a', VERSIONS => 1}
end
describe 'dewa_meter_status'
exit
