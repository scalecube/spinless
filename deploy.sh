for directory in `find ./charts -type d -maxdepth 1 -mindepth 1`
          do
              echo helm package for $directory
              helm lint --strict $directory || exit 42
              helm template --debug $directory
              helm package --debug $directory
              name=$(cat $directory/Chart.yaml | grep ^name: | cut -d: -f2 | cut -c 2-)
              pkg=$name-$(cat $directory/Chart.yaml | grep ^version: | cut -d: -f2 | cut -c 2-).tgz
              curl -sSf -u helman:P6rKHx5WkyWMCXbqRT4rsu3EgvBXfY -X PUT -T $pkg https://jfrog.nebula.exberry.io:443/artifactory/helm/scalecube/$name/$pkg
          done
