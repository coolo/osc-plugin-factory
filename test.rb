#! /usr/bin/ruby

require 'xmlhash'

sources=Hash.new
IO.popen("osc ls home:coolo:carwos", "r").read().split.each do |l|
  sources[l] = 1
end

xml = IO.popen("osc prjresults home:coolo:carwos --xml", "r").read()
xml = Xmlhash.parse(xml)
fails=Hash.new
xml.elements('result') do |repo|
  repo.elements('status') do |package|
    next unless package['code'] == 'unresolvable'
    package['details'].split(',').each do |line|
      line.strip!
      next unless line =~ /nothing provides (\S*)/
      fails[Regexp.last_match(1)] = 1
    end
  end
end

xml = open('2050fe6b710482afcbcae6585b12ee4655f4bc8f1f5daec19e15148daad0facc-primary.xml').read()
xml = Xmlhash.parse(xml)

links=Hash.new
xml.elements('package') do |package|
  package['format']['rpm:provides'].elements('rpm:entry') do |provide|
    if fails.include? provide['name']
      source = package['format'].value('rpm:sourcerpm') 
      if source =~ /^(.*)-([^-])*-([^-])*.src.rpm/
        links[Regexp.last_match(1)] = provide['name']
      end
    end
  end
end

xml = IO.popen("osc ls home:coolo:carwos", "r").read()
xml = Xmlhash.parse(xml)


links.keys.sort.each do |link|
  next if sources.include? link
  puts("osc copypac openSUSE:Factory #{link} home:coolo:carwos # #{links[link]}")
end
